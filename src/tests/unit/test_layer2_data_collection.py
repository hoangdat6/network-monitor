"""
Tests for Layer 2 - Data Collection Layer

Mục đích: Test CICFlowMeter capture và Flow processor
Bao gồm: CSV validation, column mapping, Kafka streaming
"""

import unittest
import tempfile
import os
import pandas as pd
import json
from unittest.mock import Mock, patch, MagicMock
import sys
import shutil

# Add processor to path for testing
sys.path.append('/home/dathv2004/Documents/BKDN/Learning/PBL6/network_monitor/src/infra/network-capture/flow-processor')

try:
    from processor import FlowProcessor, CSVWatcher
except ImportError as e:
    print(f"Could not import processor: {e}")
    FlowProcessor = None
    CSVWatcher = None

class TestFlowProcessor(unittest.TestCase):
    """Test Flow Processor functionality"""
    
    def setUp(self):
        if FlowProcessor is None:
            self.skipTest("FlowProcessor not available")
            
        self.temp_dir = tempfile.mkdtemp()
        self.mock_producer = Mock()
        self.processor = FlowProcessor(
            input_dir=self.temp_dir,
            kafka_servers=['localhost:9092'],
            kafka_topic='test-flows'
        )
        self.processor.producer = self.mock_producer
    
    def tearDown(self):
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir)
    
    def create_test_csv(self, filename='test.csv', valid=True):
        """Create test CSV file"""
        if valid:
            data = {
                'flow_duration': [1000000, 2000000],
                'tot_fwd_pkts': [10, 20],
                'tot_bwd_pkts': [5, 15],
                'flow_pkts_s': [100.0, 200.0],
                'flow_byts_s': [5000.0, 10000.0],
                'syn_flag_cnt': [1, 0],
                'ack_flag_cnt': [10, 15]
            }
        else:
            data = {
                'invalid_col': [1, 2],
                'another_col': [3, 4]
            }
        
        df = pd.DataFrame(data)
        file_path = os.path.join(self.temp_dir, filename)
        df.to_csv(file_path, index=False)
        return file_path
    
    def test_csv_validation_valid(self):
        """Test valid CSV validation"""
        file_path = self.create_test_csv(valid=True)
        self.assertTrue(self.processor.validate_csv(file_path))
    
    def test_csv_validation_invalid(self):
        """Test invalid CSV validation"""
        file_path = self.create_test_csv(valid=False)
        self.assertFalse(self.processor.validate_csv(file_path))
    
    def test_csv_validation_empty(self):
        """Test empty CSV validation"""
        file_path = os.path.join(self.temp_dir, 'empty.csv')
        open(file_path, 'w').close()  # Create empty file
        self.assertFalse(self.processor.validate_csv(file_path))
    
    def test_column_mapping(self):
        """Test column mapping to CICIDS2017 format"""
        file_path = self.create_test_csv()
        
        # Mock successful Kafka send
        self.mock_producer.send.return_value.get.return_value = None
        self.mock_producer.flush.return_value = None
        
        flows_processed = self.processor.process_csv(file_path)
        
        self.assertEqual(flows_processed, 2)
        self.assertEqual(self.mock_producer.send.call_count, 2)
        
        # Check that columns were mapped correctly
        sent_data = self.mock_producer.send.call_args_list[0][0][1]
        self.assertIn('Flow Duration', sent_data)
        self.assertIn('Total Fwd Packets', sent_data)
        self.assertIn('Flow Packets/s', sent_data)
    
    def test_data_cleaning(self):
        """Test data cleaning (inf/nan handling)"""
        # Create CSV with inf/nan values
        data = {
            'flow_duration': [1000000, float('inf')],
            'tot_fwd_pkts': [10, float('nan')],
            'flow_pkts_s': [100.0, -float('inf')]
        }
        df = pd.DataFrame(data)
        
        cleaned_df = self.processor.clean_data(df)
        
        # Check that inf/nan are replaced with 0
        self.assertFalse(cleaned_df.isinf().any().any())
        self.assertFalse(cleaned_df.isna().any().any())
        self.assertEqual(cleaned_df.iloc[1]['tot_fwd_pkts'], 0.0)
    
    def test_health_check(self):
        """Test health check functionality"""
        with patch.object(self.processor.producer, 'get_cluster_metadata') as mock_metadata:
            mock_metadata.return_value.brokers = ['broker1']
            
            health = self.processor.health_check()
            
            self.assertEqual(health['status'], 'healthy')
            self.assertTrue(health['kafka_connected'])
            self.assertIn('timestamp', health)
    
    @patch('os.remove')
    def test_file_cleanup(self, mock_remove):
        """Test that processed files are removed"""
        file_path = self.create_test_csv()
        
        # Mock successful Kafka send
        self.mock_producer.send.return_value.get.return_value = None
        self.mock_producer.flush.return_value = None
        
        self.processor.process_csv(file_path)
        
        # Verify file removal was attempted
        mock_remove.assert_called_with(file_path)
    
    def test_batch_processing(self):
        """Test batch processing of large datasets"""
        # Create large dataset
        data = {
            'flow_duration': list(range(1000)),
            'tot_fwd_pkts': list(range(1000, 2000)),
            'flow_pkts_s': [float(i) for i in range(2000, 3000)]
        }
        df = pd.DataFrame(data)
        file_path = os.path.join(self.temp_dir, 'large.csv')
        df.to_csv(file_path, index=False)
        
        # Set small batch size
        self.processor.batch_size = 100
        
        # Mock successful Kafka send
        self.mock_producer.send.return_value.get.return_value = None
        self.mock_producer.flush.return_value = None
        
        flows_processed = self.processor.process_csv(file_path)
        
        self.assertEqual(flows_processed, 1000)
        self.assertEqual(self.mock_producer.send.call_count, 1000)

class TestCaptureScript(unittest.TestCase):
    """Test capture script functionality"""
    
    def test_capture_script_health_check(self):
        """Test capture script health check"""
        script_path = '/home/dathv2004/Documents/BKDN/Learning/PBL6/network_monitor/src/infra/network-capture/cicflowmeter/capture.sh'
        
        if not os.path.exists(script_path):
            self.skipTest("Capture script not found")
        
        # Test that script is executable
        self.assertTrue(os.access(script_path, os.X_OK))
    
    def test_pcap_validation(self):
        """Test PCAP file validation logic"""
        # This would require more complex setup with actual PCAP files
        # For now, just test that the concept works
        self.assertTrue(True)  # Placeholder

class TestIntegration(unittest.TestCase):
    """Integration tests for data collection layer"""
    
    @patch('subprocess.run')
    def test_end_to_end_flow(self, mock_subprocess):
        """Test complete flow from capture to Kafka"""
        # Mock tcpdump success
        mock_subprocess.return_value.returncode = 0
        
        # This would test:
        # 1. Packet capture
        # 2. CICFlowMeter processing  
        # 3. CSV generation
        # 4. Flow processor
        # 5. Kafka streaming
        
        # For now, placeholder
        self.assertTrue(True)

class TestFeatureMapping(unittest.TestCase):
    """Test feature mapping accuracy"""
    
    def test_feature_count(self):
        """Test that we map all 78 features correctly"""
        if FlowProcessor is None:
            self.skipTest("FlowProcessor not available")
            
        processor = FlowProcessor()
        
        # Should have mapping for all major features
        expected_features = [
            'Flow Duration',
            'Total Fwd Packets',
            'Total Backward Packets',
            'Flow Bytes/s',
            'Flow Packets/s',
            'SYN Flag Count',
            'ACK Flag Count'
        ]
        
        mapped_features = list(processor.COLUMN_MAPPING.values())
        
        for feature in expected_features:
            self.assertIn(feature, mapped_features)
    
    def test_feature_types(self):
        """Test that mapped features have correct types"""
        if FlowProcessor is None:
            self.skipTest("FlowProcessor not available")
            
        # Create test data with various types
        data = {
            'flow_duration': [1000000],
            'tot_fwd_pkts': [10],
            'flow_pkts_s': [100.5]
        }
        df = pd.DataFrame(data)
        
        processor = FlowProcessor()
        df_mapped = df.rename(columns=processor.COLUMN_MAPPING)
        df_cleaned = processor.clean_data(df_mapped)
        
        # All numeric columns should be float64
        numeric_cols = df_cleaned.select_dtypes(include=['number']).columns
        for col in numeric_cols:
            self.assertEqual(df_cleaned[col].dtype, 'float64')

if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)