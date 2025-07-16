#!/usr/bin/env python3
"""
S3 Configuration Setup Script
Helps configure AWS S3 credentials and bucket settings
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

def setup_s3_config():
    """Interactive setup for S3 configuration"""
    print("🔧 S3 Configuration Setup")
    print("=" * 40)
    
    # Load existing environment
    backend_env_path = Path(__file__).parent.parent / "Backend.env"
    load_dotenv(backend_env_path)
    
    # Get current values
    current_values = {
        'AWS_ACCESS_KEY_ID': os.getenv('AWS_ACCESS_KEY_ID', ''),
        'AWS_SECRET_ACCESS_KEY': os.getenv('AWS_SECRET_ACCESS_KEY', ''),
        'S3_BUCKET_NAME': os.getenv('S3_BUCKET_NAME', 'mydscvr-event-images'),
        'AWS_REGION': os.getenv('AWS_REGION', 'me-central-1')
    }
    
    print("Current configuration:")
    for key, value in current_values.items():
        display_value = value if key != 'AWS_SECRET_ACCESS_KEY' else ('*' * len(value) if value else '')
        print(f"  {key}: {display_value}")
    
    print("\nEnter new values (press Enter to keep current):")
    
    new_values = {}
    for key, current in current_values.items():
        if key == 'AWS_SECRET_ACCESS_KEY':
            prompt = f"{key} (hidden): "
        else:
            prompt = f"{key} [{current}]: "
            
        new_value = input(prompt).strip()
        if new_value:
            new_values[key] = new_value
        elif current:
            new_values[key] = current
    
    # Validate required fields
    required_fields = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'S3_BUCKET_NAME']
    missing_fields = [field for field in required_fields if not new_values.get(field)]
    
    if missing_fields:
        print(f"\n❌ Missing required fields: {', '.join(missing_fields)}")
        return False
    
    # Update Backend.env file
    try:
        # Read existing file
        if backend_env_path.exists():
            with open(backend_env_path, 'r') as f:
                lines = f.readlines()
        else:
            lines = []
        
        # Update or add new values
        updated_lines = []
        updated_keys = set()
        
        for line in lines:
            if '=' in line:
                key = line.split('=')[0].strip()
                if key in new_values:
                    updated_lines.append(f"{key}={new_values[key]}\n")
                    updated_keys.add(key)
                else:
                    updated_lines.append(line)
            else:
                updated_lines.append(line)
        
        # Add new keys that weren't in the file
        for key, value in new_values.items():
            if key not in updated_keys:
                updated_lines.append(f"{key}={value}\n")
        
        # Write updated file
        with open(backend_env_path, 'w') as f:
            f.writelines(updated_lines)
            
        print(f"\n✅ Configuration saved to {backend_env_path}")
        
        # Test S3 connection
        test_s3_connection(new_values)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to save configuration: {e}")
        return False

def test_s3_connection(config):
    """Test S3 connection with provided configuration"""
    print("\n🔍 Testing S3 connection...")
    
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        # Create S3 client
        s3_client = boto3.client(
            's3',
            region_name=config['AWS_REGION'],
            aws_access_key_id=config['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=config['AWS_SECRET_ACCESS_KEY']
        )
        
        # Test bucket access
        bucket_name = config['S3_BUCKET_NAME']
        
        # Check if bucket exists
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            print(f"✅ Successfully connected to bucket: {bucket_name}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                print(f"⚠️  Bucket '{bucket_name}' not found. Creating it...")
                try:
                    if config['AWS_REGION'] == 'us-east-1':
                        s3_client.create_bucket(Bucket=bucket_name)
                    else:
                        s3_client.create_bucket(
                            Bucket=bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': config['AWS_REGION']}
                        )
                    print(f"✅ Created bucket: {bucket_name}")
                except Exception as create_error:
                    print(f"❌ Failed to create bucket: {create_error}")
                    return False
            else:
                print(f"❌ Bucket access failed: {e}")
                return False
        
        # Test upload permissions
        try:
            test_key = "test/connection_test.txt"
            s3_client.put_object(
                Bucket=bucket_name,
                Key=test_key,
                Body=b"S3 connection test",
                ContentType='text/plain'
            )
            print("✅ Upload permissions verified")
            
            # Clean up test file
            s3_client.delete_object(Bucket=bucket_name, Key=test_key)
            print("✅ Delete permissions verified")
            
        except Exception as e:
            print(f"❌ Upload/delete test failed: {e}")
            return False
        
        return True
        
    except ImportError:
        print("❌ boto3 not installed. Please install: pip install boto3")
        return False
    except Exception as e:
        print(f"❌ S3 connection test failed: {e}")
        return False

def show_next_steps():
    """Show next steps after configuration"""
    print("\n🎯 Next Steps:")
    print("=" * 40)
    print("1. Install required packages:")
    print("   pip install boto3")
    print("\n2. Run the image migration script:")
    print("   python Backend/scripts/migrate_images_to_s3.py")
    print("\n3. Update your applications to use S3 storage")
    print("\n4. Test image generation and storage")

def main():
    """Main configuration function"""
    print("🚀 S3 Storage Configuration")
    print("=" * 40)
    
    # Check if boto3 is installed
    try:
        import boto3
        print("✅ boto3 is installed")
    except ImportError:
        print("⚠️  boto3 not installed. Please install: pip install boto3")
        response = input("Continue anyway? (y/N): ").lower().strip()
        if response != 'y':
            return
    
    # Setup configuration
    if setup_s3_config():
        show_next_steps()
        
        # Ask about migration
        print("\n" + "=" * 40)
        response = input("Run image migration now? (y/N): ").lower().strip()
        if response == 'y':
            print("Starting migration...")
            import subprocess
            try:
                subprocess.run([sys.executable, "Backend/scripts/migrate_images_to_s3.py"], check=True)
            except subprocess.CalledProcessError as e:
                print(f"❌ Migration failed: {e}")
    else:
        print("❌ Configuration failed")

if __name__ == "__main__":
    main()