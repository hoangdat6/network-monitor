#!/usr/bin/env python3
"""
Comprehensive Test Suite for Data Processing Components

Mục đích: Test tất cả components của Layer 4 - Data Processing
Bao gồm: Feature Normalizer, Batch Processor, Stream Processor, Data Quality Checker
Loại test: Unit tests, Integration tests, Performance tests
"""

import unittest
import pandas as pd
import numpy as np
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
import os
from datetime import datetime, timedelta
import asyncio
import threading
import time

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Mock external dependencies for testing
class MockKafkaProducer:
    def __init__(self, *args, **kwargs):
        self.sent_messages = []
        
    def send(self, topic, key=None, value=None):
        self.sent_messages.append({'topic': topic, 'key': key, 'value': value})
        # Return mock future
        future = Mock()
        future.get.return_value = Mock()
        return future
        
    def flush(self, timeout=None):
        pass
        
    def close(self):
        pass

class MockKafkaConsumer:
    def __init__(self, *topics, **kwargs):
        self.topics = topics
        self.kwargs = kwargs
        self.messages = []
        self._closed = False
        
    def poll(self, timeout_ms=100):
        if self.messages and not self._closed:
            message = self.messages.pop(0)
            return {('test-topic', 0): [message]}
        return {}
        
    def commit(self):
        pass
        
    def close(self):
        self._closed = True

# Mock external imports
sys.modules['kafka'] = Mock()
sys.modules['kafka'].KafkaProducer = MockKafkaProducer
sys.modules['kafka'].KafkaConsumer = MockKafkaConsumer

sys.modules['watchdog'] = Mock()
sys.modules['watchdog.observers'] = Mock()
sys.modules['watchdog.events'] = Mock()

# Now import our modules
try:
    from infra.data_processing.feature_normalizer import FeatureNormalizer
    from infra.data_processing.batch_processor import BatchProcessor, BatchConfig
    from infra.data_processing.stream_processor import StreamProcessor, StreamConfig, WindowConfig
    from infra.data_processing.data_quality_checker import DataQualityChecker, Severity, QualityReport
except ImportError as e:
    print(f"Import error: {e}")
    # Create mock classes for testing if imports fail
    class FeatureNormalizer:
        def __init__(self, *args, **kwargs): pass
        def fit(self, df): return self
        def transform(self, df): return df
        def fit_transform(self, df): return df
        
    class BatchProcessor:
        def __init__(self, config): pass
        
    class StreamProcessor:
        def __init__(self, config): pass
        
    class DataQualityChecker:
        def __init__(self): pass
        def validate(self, df): return QualityReport()


class TestFeatureNormalizer(unittest.TestCase):
    """Test Feature Normalizer functionality"""
    
    def setUp(self):
        """Setup test data"""
        np.random.seed(42)
        self.n_samples = 100
        
        # Create realistic test data
        self.test_data = {
            'flow_duration': np.random.exponential(50000, self.n_samples),
            'tot_fwd_pkts': np.random.poisson(10, self.n_samples),
            'tot_bwd_pkts': np.random.poisson(8, self.n_samples),
            'flow_byts_s': np.random.exponential(1000000, self.n_samples),
            'flow_pkts_s': np.random.exponential(100, self.n_samples),
            'pkt_len_mean': np.random.normal(500, 200, self.n_samples),
            'protocol': np.random.choice([6, 17, 1], self.n_samples),
            'label': np.random.choice(['BENIGN', 'DDoS'], self.n_samples)
        }
        
        # Add some NaN values
        nan_indices = np.random.choice(self.n_samples, 10, replace=False)
        self.test_data['pkt_len_mean'][nan_indices] = np.nan
        
        self.df = pd.DataFrame(self.test_data)
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Cleanup"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_normalizer_initialization(self):
        """Test normalizer initialization"""
        # Test different methods
        for method in ['standard', 'minmax', 'robust']:
            normalizer = FeatureNormalizer(method=method)
            self.assertEqual(normalizer.method, method)
            self.assertFalse(normalizer.is_fitted)
            
        # Test invalid method
        with self.assertRaises(ValueError):
            FeatureNormalizer(method='invalid')
            
    def test_data_validation(self):
        """Test data validation functionality"""
        normalizer = FeatureNormalizer()
        
        # Valid data
        is_valid, errors = normalizer.validate_data(self.df)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Empty DataFrame
        empty_df = pd.DataFrame()
        is_valid, errors = normalizer.validate_data(empty_df)
        self.assertFalse(is_valid)
        self.assertIn("DataFrame is empty", str(errors))
        
        # Invalid data types
        bad_df = self.df.copy()
        bad_df['tot_fwd_pkts'] = bad_df['tot_fwd_pkts'].astype(str)
        is_valid, errors = normalizer.validate_data(bad_df)
        # Should still be valid as it only checks for completely missing columns
        
    def test_fit_transform(self):
        """Test fit and transform functionality"""
        normalizer = FeatureNormalizer(method='standard')
        
        # Fit transform
        df_normalized = normalizer.fit_transform(self.df)
        
        # Check that normalizer is fitted
        self.assertTrue(normalizer.is_fitted)
        
        # Check output shape
        self.assertEqual(df_normalized.shape, self.df.shape)
        
        # Check that numeric features are normalized
        numeric_features = normalizer._get_numeric_features()
        available_features = [f for f in numeric_features if f in df_normalized.columns]
        
        for feature in available_features:
            if feature in normalizer.feature_names:
                # Should have mean close to 0 and std close to 1 (approximately)
                values = df_normalized[feature].dropna()
                if len(values) > 1:
                    self.assertAlmostEqual(values.mean(), 0, delta=0.1)
                    self.assertAlmostEqual(values.std(), 1, delta=0.1)
                    
    def test_inverse_transform(self):
        """Test inverse transformation"""
        normalizer = FeatureNormalizer(method='standard')
        
        # Fit and transform
        df_normalized = normalizer.fit_transform(self.df)
        
        # Inverse transform
        df_reconstructed = normalizer.inverse_transform(df_normalized)
        
        # Check shapes match
        self.assertEqual(df_reconstructed.shape, self.df.shape)
        
        # Check reconstruction quality for numeric features
        numeric_features = normalizer.feature_names
        original_numeric = self.df[numeric_features].fillna(self.df[numeric_features].median())
        reconstructed_numeric = df_reconstructed[numeric_features]
        
        # Should be close to original (allowing for floating point errors)
        mse = np.mean((original_numeric - reconstructed_numeric) ** 2)
        self.assertLess(mse, 1e-10)  # Very small MSE
        
    def test_save_load_scalers(self):
        """Test saving and loading scalers"""
        normalizer = FeatureNormalizer(save_path=self.temp_dir)
        
        # Fit normalizer
        normalizer.fit(self.df)
        
        # Save scalers
        normalizer.save_scalers()
        
        # Create new normalizer and load
        new_normalizer = FeatureNormalizer()
        new_normalizer.load_scalers(self.temp_dir)
        
        # Check that it was loaded correctly
        self.assertTrue(new_normalizer.is_fitted)
        self.assertEqual(new_normalizer.method, normalizer.method)
        self.assertEqual(new_normalizer.feature_names, normalizer.feature_names)
        
        # Test transformation consistency
        df_normalized1 = normalizer.transform(self.df)
        df_normalized2 = new_normalizer.transform(self.df)
        
        # Should produce same results
        pd.testing.assert_frame_equal(df_normalized1, df_normalized2)
        
    def test_feature_importance(self):
        """Test feature importance calculation"""
        normalizer = FeatureNormalizer()
        normalizer.fit(self.df)
        
        importance = normalizer.get_feature_importance_by_variance()
        
        # Should be a dictionary
        self.assertIsInstance(importance, dict)
        
        # Should have entries for fitted features
        self.assertGreater(len(importance), 0)
        
        # Values should be between 0 and 1
        for feature, score in importance.items():
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 1)
            
    def test_generate_report(self):
        """Test report generation"""
        normalizer = FeatureNormalizer()
        normalizer.fit(self.df)
        
        report = normalizer.generate_report()
        
        # Check report structure
        required_keys = ['method', 'total_features', 'feature_stats', 'feature_importance']
        for key in required_keys:
            self.assertIn(key, report)
            
        # Check feature stats
        self.assertIsInstance(report['feature_stats'], dict)
        self.assertIn('mean', report['feature_stats'])
        self.assertIn('std', report['feature_stats'])


class TestBatchProcessor(unittest.TestCase):
    """Test Batch Processor functionality"""
    
    def setUp(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test directories
        self.input_dir = Path(self.temp_dir) / "input"
        self.processed_dir = Path(self.temp_dir) / "processed"
        self.error_dir = Path(self.temp_dir) / "errors"
        
        for dir_path in [self.input_dir, self.processed_dir, self.error_dir]:
            dir_path.mkdir(parents=True)
            
        # Create test configuration
        self.config = BatchConfig(
            input_directory=str(self.input_dir),
            processed_directory=str(self.processed_dir),
            error_directory=str(self.error_dir),
            chunk_size=10,
            max_workers=2,
            enable_normalization=False  # Disable for testing
        )
        
    def tearDown(self):
        """Cleanup"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_batch_config(self):
        """Test batch configuration"""
        config = BatchConfig()
        
        # Check defaults
        self.assertEqual(config.chunk_size, 1000)
        self.assertEqual(config.kafka_servers, ["localhost:9092"])
        self.assertIsNotNone(config.file_patterns)
        
        # Test custom values
        custom_config = BatchConfig(
            chunk_size=500,
            kafka_servers=["server1:9092", "server2:9092"]
        )
        self.assertEqual(custom_config.chunk_size, 500)
        self.assertEqual(len(custom_config.kafka_servers), 2)
        
    def test_directory_setup(self):
        """Test directory creation"""
        processor = BatchProcessor(self.config)
        
        # Check directories exist
        self.assertTrue(self.input_dir.exists())
        self.assertTrue(self.processed_dir.exists())
        self.assertTrue(self.error_dir.exists())
        
    def test_csv_reading(self):
        """Test CSV chunk reading"""
        # Create test CSV file
        test_data = pd.DataFrame({
            'flow_duration': range(100),
            'tot_fwd_pkts': range(100, 200),
            'tot_bwd_pkts': range(200, 300),
            'label': ['BENIGN'] * 100
        })
        
        test_file = self.input_dir / "test.csv"
        test_data.to_csv(test_file, index=False)
        
        processor = BatchProcessor(self.config)
        
        # Read chunks
        chunks = list(processor.read_csv_chunks(test_file, chunk_size=20))
        
        # Should have 5 chunks of 20 rows each
        self.assertEqual(len(chunks), 5)
        for chunk in chunks:
            self.assertEqual(len(chunk), 20)
            
    def test_chunk_processing(self):
        """Test individual chunk processing"""
        processor = BatchProcessor(self.config)
        
        # Create test chunk
        chunk = pd.DataFrame({
            'flow_duration': [1000, 2000, 3000],
            'tot_fwd_pkts': [10, 20, 30],
            'tot_bwd_pkts': [5, 15, 25],
            'label': ['BENIGN', 'DDoS', 'BENIGN']
        })
        
        records, stats = processor.process_chunk(chunk, "test_chunk")
        
        # Check records
        self.assertEqual(len(records), 3)
        for record in records:
            self.assertIn('chunk_id', record)
            self.assertIn('record_id', record)
            self.assertIn('data', record)
            self.assertEqual(record['chunk_id'], "test_chunk")
            
        # Check stats
        self.assertEqual(stats['records_count'], 3)
        self.assertGreater(stats['processing_time'], 0)


class TestStreamProcessor(unittest.TestCase):
    """Test Stream Processor functionality"""
    
    def setUp(self):
        """Setup test environment"""
        self.config = StreamConfig(
            input_topics=["test-topic"],
            output_topic="test-output",
            window_config=WindowConfig(
                size_seconds=60,
                slide_seconds=10,
                grace_seconds=30
            ),
            enable_anomaly_detection=True
        )
        
    def test_stream_config(self):
        """Test stream configuration"""
        config = StreamConfig()
        
        # Check defaults
        self.assertIsNotNone(config.input_topics)
        self.assertIsNotNone(config.kafka_servers)
        self.assertIsNotNone(config.window_config)
        
    def test_window_creation(self):
        """Test time window creation"""
        with patch('infra.data_processing.stream_processor.KafkaConsumer', MockKafkaConsumer), \
             patch('infra.data_processing.stream_processor.KafkaProducer', MockKafkaProducer):
            
            processor = StreamProcessor(self.config)
            
            # Test window alignment
            test_time = datetime(2024, 1, 1, 12, 0, 0)
            aligned_time = processor._align_to_window(test_time)
            
            # Should align to slide boundaries
            self.assertIsInstance(aligned_time, datetime)
            
            # Test window creation
            window = processor._create_window(test_time)
            self.assertIsNotNone(window)
            self.assertEqual(window.window_id, processor._get_window_id(test_time))
            
    def test_message_processing(self):
        """Test individual message processing"""
        with patch('infra.data_processing.stream_processor.KafkaConsumer', MockKafkaConsumer), \
             patch('infra.data_processing.stream_processor.KafkaProducer', MockKafkaProducer):
            
            processor = StreamProcessor(self.config)
            
            # Create mock message
            mock_message = Mock()
            mock_message.value = {
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'flow_duration': 1000,
                    'tot_fwd_pkts': 10,
                    'tot_bwd_pkts': 5
                }
            }
            
            # Process message
            result = processor.process_message(mock_message)
            
            # Should succeed
            self.assertTrue(result)
            self.assertEqual(processor.stats.messages_processed, 1)


class TestDataQualityChecker(unittest.TestCase):
    """Test Data Quality Checker functionality"""
    
    def setUp(self):
        """Setup test data"""
        np.random.seed(42)
        self.n_samples = 100
        
        # Create test data with various quality issues
        self.test_data = {
            'flow_duration': np.random.exponential(50000, self.n_samples),
            'tot_fwd_pkts': np.random.poisson(10, self.n_samples),
            'tot_bwd_pkts': np.random.poisson(8, self.n_samples),
            'src_port': np.random.randint(1, 65536, self.n_samples),
            'dst_port': np.random.randint(1, 65536, self.n_samples),
            'protocol': np.random.choice([6, 17, 1], self.n_samples),
            'timestamp': pd.date_range('2024-01-01', periods=self.n_samples, freq='1S'),
            'label': np.random.choice(['BENIGN', 'DDoS'], self.n_samples)
        }
        
        # Introduce quality issues
        
        # Missing values
        self.test_data['flow_duration'][0:5] = np.nan
        
        # Invalid port numbers
        self.test_data['src_port'][5:8] = -1  # Invalid negative ports
        self.test_data['dst_port'][8:10] = 70000  # Invalid high ports
        
        # Negative packet counts
        self.test_data['tot_fwd_pkts'][10:12] = -5
        
        self.df = pd.DataFrame(self.test_data)
        
    def test_quality_checker_initialization(self):
        """Test quality checker initialization"""
        checker = DataQualityChecker()
        
        # Should have default rules
        self.assertGreater(len(checker.rules), 0)
        
    def test_schema_validation(self):
        """Test schema validation rule"""
        from infra.data_processing.data_quality_checker import SchemaValidationRule
        
        # Valid schema
        rule = SchemaValidationRule(
            expected_columns=list(self.df.columns),
            required_columns=['tot_fwd_pkts', 'tot_bwd_pkts']
        )
        
        issues = rule.validate(self.df)
        self.assertEqual(len(issues), 0)  # No issues expected
        
        # Missing required column
        df_missing = self.df.drop('tot_fwd_pkts', axis=1)
        issues = rule.validate(df_missing)
        self.assertGreater(len(issues), 0)  # Should have issues
        
    def test_null_validation(self):
        """Test null validation rule"""
        from infra.data_processing.data_quality_checker import NullValidationRule
        
        rule = NullValidationRule(
            max_null_ratio=0.01,  # Very strict
            critical_columns=['tot_fwd_pkts']
        )
        
        issues = rule.validate(self.df)
        
        # Should find null issues
        self.assertGreater(len(issues), 0)
        
        # Check that flow_duration null issue is detected
        null_issues = [issue for issue in issues if 'flow_duration' in issue.message]
        self.assertGreater(len(null_issues), 0)
        
    def test_range_validation(self):
        """Test range validation rule"""
        from infra.data_processing.data_quality_checker import RangeValidationRule
        
        rule = RangeValidationRule({
            'src_port': (1, 65535),
            'dst_port': (1, 65535),
            'tot_fwd_pkts': (0, 1000)
        })
        
        issues = rule.validate(self.df)
        
        # Should find range issues (negative ports, negative packets)
        self.assertGreater(len(issues), 0)
        
        # Check for port range issues
        port_issues = [issue for issue in issues if 'port' in issue.message.lower()]
        self.assertGreater(len(port_issues), 0)
        
    def test_network_validation(self):
        """Test network-specific validation"""
        from infra.data_processing.data_quality_checker import NetworkSpecificValidationRule
        
        rule = NetworkSpecificValidationRule()
        
        issues = rule.validate(self.df)
        
        # Should find negative packet count issues
        packet_issues = [issue for issue in issues if 'negative packet' in issue.message.lower()]
        self.assertGreater(len(packet_issues), 0)
        
    def test_full_validation(self):
        """Test complete validation workflow"""
        checker = DataQualityChecker()
        
        report = checker.validate(self.df)
        
        # Check report structure
        self.assertIsInstance(report, QualityReport)
        self.assertEqual(report.total_records, len(self.df))
        self.assertGreater(len(report.issues), 0)  # Should have issues
        
        # Check quality score calculation
        self.assertGreaterEqual(report.quality_score, 0)
        self.assertLessEqual(report.quality_score, 100)
        
    def test_report_generation(self):
        """Test report generation and export"""
        checker = DataQualityChecker()
        report = checker.validate(self.df)
        
        # Test summary generation
        summary = checker.generate_summary_report(report)
        
        self.assertIn('quality_score', summary)
        self.assertIn('total_records', summary)
        self.assertIn('issues_by_severity', summary)
        self.assertIn('top_issues', summary)
        
    def test_issue_severity_filtering(self):
        """Test filtering issues by severity"""
        checker = DataQualityChecker()
        report = checker.validate(self.df)
        
        # Test severity filtering
        critical_issues = report.get_issues_by_severity(Severity.CRITICAL)
        error_issues = report.get_issues_by_severity(Severity.ERROR)
        warning_issues = report.get_issues_by_severity(Severity.WARNING)
        
        # Should be lists
        self.assertIsInstance(critical_issues, list)
        self.assertIsInstance(error_issues, list)
        self.assertIsInstance(warning_issues, list)


class TestIntegration(unittest.TestCase):
    """Integration tests for data processing pipeline"""
    
    def setUp(self):
        """Setup integration test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Cleanup"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_normalizer_quality_checker_integration(self):
        """Test integration between normalizer and quality checker"""
        # Create test data
        np.random.seed(42)
        df = pd.DataFrame({
            'flow_duration': np.random.exponential(50000, 100),
            'tot_fwd_pkts': np.random.poisson(10, 100),
            'tot_bwd_pkts': np.random.poisson(8, 100),
            'label': np.random.choice(['BENIGN', 'DDoS'], 100)
        })
        
        # First check quality
        quality_checker = DataQualityChecker()
        quality_report = quality_checker.validate(df)
        
        # Then normalize
        normalizer = FeatureNormalizer()
        df_normalized = normalizer.fit_transform(df)
        
        # Check quality of normalized data
        normalized_quality_report = quality_checker.validate(df_normalized)
        
        # Normalized data should generally have same or better quality
        self.assertIsInstance(quality_report, QualityReport)
        self.assertIsInstance(normalized_quality_report, QualityReport)
        
    def test_end_to_end_data_flow(self):
        """Test end-to-end data processing flow"""
        # Create sample CSV file
        df = pd.DataFrame({
            'flow_duration': range(50),
            'tot_fwd_pkts': range(50, 100),
            'tot_bwd_pkts': range(100, 150),
            'timestamp': pd.date_range('2024-01-01', periods=50, freq='1S'),
            'label': ['BENIGN'] * 50
        })
        
        csv_file = Path(self.temp_dir) / "test_flows.csv"
        df.to_csv(csv_file, index=False)
        
        # Step 1: Quality check
        quality_checker = DataQualityChecker()
        quality_report = quality_checker.validate(df)
        
        # Step 2: Normalization
        normalizer = FeatureNormalizer()
        df_normalized = normalizer.fit_transform(df)
        
        # Step 3: Quality check normalized data
        normalized_quality_report = quality_checker.validate(df_normalized)
        
        # Verify the pipeline worked
        self.assertIsNotNone(quality_report)
        self.assertIsNotNone(df_normalized)
        self.assertIsNotNone(normalized_quality_report)
        
        # Check data shapes preserved
        self.assertEqual(df.shape, df_normalized.shape)


class TestPerformance(unittest.TestCase):
    """Performance tests for data processing components"""
    
    def test_normalizer_performance(self):
        """Test normalizer performance with large dataset"""
        # Create large dataset
        n_samples = 10000
        df = pd.DataFrame({
            'flow_duration': np.random.exponential(50000, n_samples),
            'tot_fwd_pkts': np.random.poisson(10, n_samples),
            'tot_bwd_pkts': np.random.poisson(8, n_samples),
            'flow_byts_s': np.random.exponential(1000000, n_samples)
        })
        
        normalizer = FeatureNormalizer()
        
        # Time the operation
        start_time = time.time()
        df_normalized = normalizer.fit_transform(df)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Should complete within reasonable time (adjust threshold as needed)
        self.assertLess(processing_time, 10.0)  # 10 seconds
        self.assertEqual(len(df_normalized), n_samples)
        
    def test_quality_checker_performance(self):
        """Test quality checker performance"""
        # Create large dataset with quality issues
        n_samples = 5000
        df = pd.DataFrame({
            'flow_duration': np.random.exponential(50000, n_samples),
            'tot_fwd_pkts': np.random.poisson(10, n_samples),
            'tot_bwd_pkts': np.random.poisson(8, n_samples),
            'src_port': np.random.randint(1, 65536, n_samples),
            'dst_port': np.random.randint(1, 65536, n_samples)
        })
        
        # Add some quality issues
        df.iloc[0:50, 0] = np.nan  # Missing values
        df.iloc[50:60, 3] = -1     # Invalid ports
        
        checker = DataQualityChecker()
        
        # Time the validation
        start_time = time.time()
        report = checker.validate(df)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(processing_time, 5.0)  # 5 seconds
        self.assertGreater(len(report.issues), 0)


def run_all_tests():
    """Run all test suites"""
    print("Running Data Processing Layer Tests...")
    print("=" * 50)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestFeatureNormalizer,
        TestBatchProcessor,
        TestStreamProcessor,
        TestDataQualityChecker,
        TestIntegration,
        TestPerformance
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print("\nFailures:")
        for test, error in result.failures:
            print(f"- {test}: {error}")
            
    if result.errors:
        print("\nErrors:")
        for test, error in result.errors:
            print(f"- {test}: {error}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)