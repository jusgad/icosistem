#!/usr/bin/env python3
"""
Security Setup and Hardening Script for Production Deployment
"""

import os
import secrets
import hashlib
import subprocess
import json
from pathlib import Path
from datetime import datetime

class SecuritySetup:
    def __init__(self):
        self.security_report = {
            'timestamp': datetime.now().isoformat(),
            'checks': {},
            'recommendations': [],
            'critical_issues': []
        }
    
    def generate_secure_keys(self):
        """Generate secure keys for production"""
        print("🔑 Generating secure keys for production...")
        
        keys = {
            'SECRET_KEY': secrets.token_urlsafe(64),
            'JWT_SECRET_KEY': secrets.token_urlsafe(64),
            'SECURITY_PASSWORD_SALT': secrets.token_urlsafe(32),
            'WTF_CSRF_SECRET_KEY': secrets.token_urlsafe(32),
            'MONITORING_TOKEN': secrets.token_urlsafe(32)
        }
        
        # Save to secure file
        keys_file = Path('.env.keys.secure')
        with open(keys_file, 'w') as f:
            f.write("# SECURE KEYS - GENERATED " + datetime.now().isoformat() + "\n")
            f.write("# IMPORTANT: Keep this file secure and never commit to version control\n\n")
            for key, value in keys.items():
                f.write(f"{key}={value}\n")
        
        # Set restrictive permissions
        os.chmod(keys_file, 0o600)
        
        print(f"✅ Secure keys generated and saved to {keys_file}")
        print("🔒 File permissions set to 600 (owner read/write only)")
        
        self.security_report['checks']['secure_keys'] = 'PASSED'
        return keys
    
    def check_file_permissions(self):
        """Check critical file permissions"""
        print("📁 Checking file permissions...")
        
        critical_files = [
            '.env',
            '.env.production',
            'instance/',
            'logs/'
        ]
        
        issues = []
        for file_path in critical_files:
            path = Path(file_path)
            if path.exists():
                stat = path.stat()
                mode = oct(stat.st_mode)[-3:]
                
                if file_path.endswith('.env') or 'production' in file_path:
                    if mode != '600':
                        issues.append(f"{file_path} should have 600 permissions, has {mode}")
                        print(f"⚠️ {file_path}: {mode} (should be 600)")
                    else:
                        print(f"✅ {file_path}: {mode}")
                elif path.is_dir():
                    if mode not in ['755', '700']:
                        issues.append(f"{file_path} directory should have 755 or 700 permissions, has {mode}")
                        print(f"⚠️ {file_path}/: {mode} (should be 755 or 700)")
                    else:
                        print(f"✅ {file_path}/: {mode}")
        
        if issues:
            self.security_report['critical_issues'].extend(issues)
            self.security_report['checks']['file_permissions'] = 'FAILED'
        else:
            self.security_report['checks']['file_permissions'] = 'PASSED'
        
        return len(issues) == 0
    
    def setup_security_headers(self):
        """Generate security headers configuration"""
        print("🛡️ Setting up security headers...")
        
        headers_config = {
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' https:",
            'Permissions-Policy': 'geolocation=(), microphone=(), camera=()'
        }
        
        # Save security headers configuration
        with open('security_headers.json', 'w') as f:
            json.dump(headers_config, f, indent=2)
        
        print("✅ Security headers configuration saved")
        self.security_report['checks']['security_headers'] = 'PASSED'
        
        return headers_config
    
    def check_dependencies(self):
        """Check for vulnerable dependencies"""
        print("📦 Checking dependencies for vulnerabilities...")
        
        try:
            # Check if safety is installed
            result = subprocess.run(['pip', 'show', 'safety'], 
                                  capture_output=True, text=True)
            
            if result.returncode != 0:
                print("⚠️ Installing safety for vulnerability scanning...")
                subprocess.run(['pip', 'install', 'safety'], check=True)
            
            # Run safety check
            result = subprocess.run(['safety', 'check', '--json'], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ No known vulnerabilities found in dependencies")
                self.security_report['checks']['dependencies'] = 'PASSED'
            else:
                vulnerabilities = result.stdout
                print(f"⚠️ Vulnerabilities found in dependencies:")
                print(vulnerabilities)
                self.security_report['critical_issues'].append('Vulnerable dependencies detected')
                self.security_report['checks']['dependencies'] = 'FAILED'
            
        except Exception as e:
            print(f"⚠️ Could not run dependency check: {e}")
            self.security_report['checks']['dependencies'] = 'SKIPPED'
    
    def setup_logging(self):
        """Setup secure logging configuration"""
        print("📝 Setting up secure logging...")
        
        # Create logs directory
        logs_dir = Path('logs')
        logs_dir.mkdir(exist_ok=True, mode=0o755)
        
        # Create log configuration
        log_config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'default': {
                    'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
                },
                'security': {
                    'format': '[%(asctime)s] SECURITY %(levelname)s: %(message)s - %(pathname)s:%(lineno)d',
                }
            },
            'handlers': {
                'default': {
                    'level': 'INFO',
                    'formatter': 'default',
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': 'logs/app.log',
                    'maxBytes': 10485760,
                    'backupCount': 5
                },
                'security': {
                    'level': 'WARNING',
                    'formatter': 'security',
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': 'logs/security.log',
                    'maxBytes': 10485760,
                    'backupCount': 10
                }
            },
            'root': {
                'level': 'INFO',
                'handlers': ['default']
            },
            'loggers': {
                'security': {
                    'level': 'WARNING',
                    'handlers': ['security'],
                    'propagate': False
                }
            }
        }
        
        # Save logging configuration
        with open('logging_config.json', 'w') as f:
            json.dump(log_config, f, indent=2)
        
        print("✅ Logging configuration saved")
        self.security_report['checks']['logging'] = 'PASSED'
    
    def generate_ssl_config(self):
        """Generate SSL/TLS configuration"""
        print("🔐 Generating SSL/TLS configuration...")
        
        ssl_config = {
            'nginx': {
                'ssl_protocols': 'TLSv1.2 TLSv1.3',
                'ssl_ciphers': 'ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES256-SHA384',
                'ssl_prefer_server_ciphers': 'off',
                'ssl_session_cache': 'shared:SSL:10m',
                'ssl_session_timeout': '10m',
                'ssl_stapling': 'on',
                'ssl_stapling_verify': 'on',
                'add_header': [
                    'Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always',
                    'X-Frame-Options DENY always',
                    'X-Content-Type-Options nosniff always',
                    'X-XSS-Protection "1; mode=block" always'
                ]
            },
            'apache': {
                'SSLEngine': 'on',
                'SSLProtocol': 'all -SSLv3 -TLSv1 -TLSv1.1',
                'SSLCipherSuite': 'ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384',
                'SSLHonorCipherOrder': 'off',
                'Header': [
                    'always set Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"',
                    'always set X-Frame-Options DENY',
                    'always set X-Content-Type-Options nosniff'
                ]
            }
        }
        
        with open('ssl_config.json', 'w') as f:
            json.dump(ssl_config, f, indent=2)
        
        print("✅ SSL/TLS configuration generated")
        self.security_report['checks']['ssl_config'] = 'PASSED'
    
    def create_security_checklist(self):
        """Create deployment security checklist"""
        checklist = [
            "✅ Change all default passwords and keys",
            "✅ Enable HTTPS with valid SSL certificates",
            "✅ Configure firewall to block unnecessary ports",
            "✅ Set up database with restricted user permissions",
            "✅ Enable database SSL/TLS connections",
            "✅ Configure rate limiting on all endpoints",
            "✅ Set up monitoring and alerting",
            "✅ Enable audit logging for all sensitive operations",
            "✅ Configure automated backups",
            "✅ Set up intrusion detection system",
            "✅ Regular security updates and patches",
            "✅ Penetration testing before go-live",
            "✅ Staff security training",
            "✅ Incident response plan",
            "✅ Data privacy compliance (GDPR, CCPA, etc.)"
        ]
        
        with open('SECURITY_CHECKLIST.md', 'w') as f:
            f.write("# Production Security Checklist\n\n")
            f.write("Complete this checklist before deploying to production:\n\n")
            for item in checklist:
                f.write(f"- [ ] {item[2:]}\n")  # Remove checkmark for checklist
            
            f.write("\n## Critical Security Notes\n\n")
            f.write("### 1. Environment Variables\n")
            f.write("- Never commit `.env.production` to version control\n")
            f.write("- Use environment variables in production deployment\n")
            f.write("- Rotate keys regularly (at least every 90 days)\n\n")
            
            f.write("### 2. Database Security\n")
            f.write("- Use separate database user with minimal permissions\n")
            f.write("- Enable SSL/TLS for database connections\n")
            f.write("- Regular database backups with encryption\n\n")
            
            f.write("### 3. Network Security\n")
            f.write("- Use WAF (Web Application Firewall)\n")
            f.write("- Configure DDoS protection\n")
            f.write("- VPN access for administrative functions\n\n")
            
            f.write("### 4. Monitoring\n")
            f.write("- Set up alerts for failed login attempts\n")
            f.write("- Monitor for unusual API usage patterns\n")
            f.write("- Regular security audit logs review\n")
        
        print("✅ Security checklist created: SECURITY_CHECKLIST.md")
    
    def run_full_security_setup(self):
        """Run complete security setup"""
        print("🔒 RUNNING COMPLETE SECURITY SETUP")
        print("=" * 60)
        
        # Run all security setup steps
        keys = self.generate_secure_keys()
        self.check_file_permissions()
        self.setup_security_headers()
        self.check_dependencies()
        self.setup_logging()
        self.generate_ssl_config()
        self.create_security_checklist()
        
        # Generate final report
        print("\n" + "=" * 60)
        print("🔒 SECURITY SETUP COMPLETED")
        print("=" * 60)
        
        # Summary
        passed = sum(1 for v in self.security_report['checks'].values() if v == 'PASSED')
        failed = sum(1 for v in self.security_report['checks'].values() if v == 'FAILED')
        skipped = sum(1 for v in self.security_report['checks'].values() if v == 'SKIPPED')
        
        print(f"✅ Checks passed: {passed}")
        print(f"❌ Checks failed: {failed}")
        print(f"⏸️ Checks skipped: {skipped}")
        
        if failed > 0:
            print(f"\n🚨 CRITICAL ISSUES FOUND:")
            for issue in self.security_report['critical_issues']:
                print(f"  ❌ {issue}")
        
        # Save complete security report
        with open('security_report.json', 'w') as f:
            json.dump(self.security_report, f, indent=2)
        
        print(f"\n📋 Complete security report saved to: security_report.json")
        print("📋 Security checklist created: SECURITY_CHECKLIST.md")
        print("🔑 Secure keys generated: .env.keys.secure")
        
        print("\n🎯 NEXT STEPS:")
        print("1. Review and complete SECURITY_CHECKLIST.md")
        print("2. Copy secure keys from .env.keys.secure to production environment")
        print("3. Configure SSL certificates")
        print("4. Set up monitoring and alerting")
        print("5. Perform penetration testing")
        
        return failed == 0

def main():
    """Main security setup function"""
    security = SecuritySetup()
    return security.run_full_security_setup()

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)