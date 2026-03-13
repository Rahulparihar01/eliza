"""
AI Enablement Platform - AWS Bedrock Model Discovery Service

Service for discovering available models in AWS Bedrock using boto3 API.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from src.models.bedrock_config import BedrockModelInfo, BedrockAuthMethod

logger = logging.getLogger(__name__)


class BedrockDiscoveryService:
    """
    Service for discovering available Bedrock models using boto3 API.
    
    This service connects directly to AWS Bedrock to list foundation models
    available in a specific region.
    """
    
    def __init__(
        self,
        aws_region: str = "us-west-2",
        auth_method: str = BedrockAuthMethod.API_KEYS,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None
    ):
        """
        Initialize Bedrock discovery service.
        
        Args:
            aws_region: AWS region to discover models in
            auth_method: Authentication method ('api_keys' or 'iam_role')
            aws_access_key_id: AWS Access Key ID (required for 'api_keys')
            aws_secret_access_key: AWS Secret Access Key (required for 'api_keys')
            aws_session_token: AWS Session Token (optional)
        """
        self.aws_region = aws_region
        self.auth_method = auth_method
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_session_token = aws_session_token
        
        logger.info(f"Initialized Bedrock discovery service for region: {aws_region}")
    
    def _get_bedrock_client(self):
        """
        Get boto3 client for Bedrock service.
        
        Returns:
            boto3 Bedrock client
        """
        if self.auth_method == BedrockAuthMethod.IAM_ROLE:
            # Use default AWS credential chain (IAM role, env vars, etc.)
            client = boto3.client('bedrock', region_name=self.aws_region)
            logger.debug(f"Created Bedrock client using IAM role for region {self.aws_region}")
        else:
            # Use explicit credentials
            session_kwargs = {
                'aws_access_key_id': self.aws_access_key_id,
                'aws_secret_access_key': self.aws_secret_access_key,
                'region_name': self.aws_region
            }
            if self.aws_session_token:
                session_kwargs['aws_session_token'] = self.aws_session_token
            
            client = boto3.client('bedrock', **session_kwargs)
            logger.debug(f"Created Bedrock client using API keys for region {self.aws_region}")
        
        return client
    
    def discover_models(
        self,
        provider_filter: Optional[str] = None,
        include_inactive: bool = False
    ) -> List[BedrockModelInfo]:
        """
        Discover available foundation models in Bedrock.
        
        Args:
            provider_filter: Filter models by provider (e.g., 'anthropic', 'meta', 'amazon')
            include_inactive: Include inactive/deprecated models
        
        Returns:
            List of discovered BedrockModelInfo objects
        
        Raises:
            ClientError: If AWS API call fails
            NoCredentialsError: If credentials are not configured
        """
        try:
            client = self._get_bedrock_client()
            
            # List foundation models
            logger.info(f"Discovering Bedrock models in region: {self.aws_region}")
            response = client.list_foundation_models()
            
            discovered_models = []
            
            for model_summary in response.get('modelSummaries', []):
                model_id = model_summary.get('modelId')
                model_name = model_summary.get('modelName', model_id)
                provider_name = model_summary.get('providerName', 'unknown')
                model_lifecycle = model_summary.get('modelLifecycle', {})
                status = model_lifecycle.get('status', 'ACTIVE')
                
                # Filter by provider if specified
                if provider_filter and provider_name.lower() != provider_filter.lower():
                    continue
                
                # Filter inactive models unless explicitly requested
                if not include_inactive and status != 'ACTIVE':
                    continue
                
                # Extract model capabilities
                inference_types = model_summary.get('inferenceTypesSupported', [])
                supports_streaming = 'ON_DEMAND' in inference_types
                
                # Extract max tokens (if available)
                max_tokens = None
                input_modalities = model_summary.get('inputModalities', [])
                output_modalities = model_summary.get('outputModalities', [])
                
                # Create BedrockModelInfo
                bedrock_model = BedrockModelInfo(
                    model_id=model_id,
                    model_name=model_name,
                    provider=provider_name.lower(),
                    is_enabled=False,  # Disabled by default, user must explicitly enable
                    max_tokens=max_tokens,
                    supports_streaming=supports_streaming
                )
                
                discovered_models.append(bedrock_model)
                
                logger.debug(
                    f"Discovered model: {model_id} (provider={provider_name}, status={status})"
                )
            
            logger.info(
                f"Discovered {len(discovered_models)} Bedrock models in region {self.aws_region}"
            )
            
            return discovered_models
            
        except NoCredentialsError as e:
            logger.error("AWS credentials not configured for Bedrock discovery")
            raise ValueError(
                "AWS credentials not configured. Please provide valid credentials or configure IAM role."
            ) from e
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"AWS Bedrock API error: {error_code} - {error_message}")
            raise ValueError(f"Failed to discover Bedrock models: {error_message}") from e
            
        except Exception as e:
            logger.error(f"Unexpected error during Bedrock model discovery: {str(e)}")
            raise
    
    def get_model_details(self, model_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific Bedrock model.
        
        Args:
            model_id: Bedrock model identifier
        
        Returns:
            Dictionary with model details
        
        Raises:
            ClientError: If AWS API call fails
        """
        try:
            client = self._get_bedrock_client()
            
            logger.info(f"Fetching details for Bedrock model: {model_id}")
            response = client.get_foundation_model(modelIdentifier=model_id)
            
            model_details = response.get('modelDetails', {})
            
            return {
                'model_id': model_details.get('modelId'),
                'model_name': model_details.get('modelName'),
                'provider_name': model_details.get('providerName'),
                'input_modalities': model_details.get('inputModalities', []),
                'output_modalities': model_details.get('outputModalities', []),
                'supported_inference_types': model_details.get('inferenceTypesSupported', []),
                'response_streaming_supported': model_details.get('responseStreamingSupported', False),
                'model_lifecycle': model_details.get('modelLifecycle', {}),
                'customizations_supported': model_details.get('customizationsSupported', [])
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(
                f"Failed to get Bedrock model details for {model_id}: {error_code} - {error_message}"
            )
            raise ValueError(f"Failed to get model details: {error_message}") from e
    
    def test_credentials(self) -> Dict[str, Any]:
        """
        Test AWS credentials and region access.
        
        Returns:
            Dictionary with test results
        """
        try:
            client = self._get_bedrock_client()
            
            # Try to list models (minimal operation)
            start_time = datetime.now()
            response = client.list_foundation_models(maxResults=1)
            end_time = datetime.now()
            
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            
            return {
                'success': True,
                'region': self.aws_region,
                'auth_method': self.auth_method,
                'response_time_ms': response_time_ms,
                'models_available': len(response.get('modelSummaries', [])) > 0,
                'message': 'Credentials valid and Bedrock accessible',
                'tested_at': datetime.now()
            }
            
        except NoCredentialsError:
            return {
                'success': False,
                'region': self.aws_region,
                'auth_method': self.auth_method,
                'error_details': 'AWS credentials not configured',
                'message': 'No valid AWS credentials found',
                'tested_at': datetime.now()
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            return {
                'success': False,
                'region': self.aws_region,
                'auth_method': self.auth_method,
                'error_details': f"{error_code}: {error_message}",
                'message': 'AWS API error during credential test',
                'tested_at': datetime.now()
            }
            
        except Exception as e:
            return {
                'success': False,
                'region': self.aws_region,
                'auth_method': self.auth_method,
                'error_details': str(e),
                'message': 'Unexpected error during credential test',
                'tested_at': datetime.now()
            }
    
    def list_available_regions(self) -> List[str]:
        """
        List AWS regions where Bedrock is available.
        
        Note: This is a static list as of 2025. In production, you might want
        to fetch this dynamically or update it periodically.
        
        Returns:
            List of AWS region names
        """
        # Bedrock regions as of 2025 (update as needed)
        return [
            'us-east-1',      # US East (N. Virginia)
            'us-west-2',      # US West (Oregon)
            'ap-southeast-1', # Asia Pacific (Singapore)
            'ap-northeast-1', # Asia Pacific (Tokyo)
            'eu-central-1',   # Europe (Frankfurt)
            'eu-west-1',      # Europe (Ireland)
            'eu-west-2',      # Europe (London)
            'eu-west-3',      # Europe (Paris)
            'ap-south-1',     # Asia Pacific (Mumbai)
            'ca-central-1',   # Canada (Central)
        ]

