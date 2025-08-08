# Production Security Checklist

Complete this checklist before deploying to production:

- [ ] Change all default passwords and keys
- [ ] Enable HTTPS with valid SSL certificates
- [ ] Configure firewall to block unnecessary ports
- [ ] Set up database with restricted user permissions
- [ ] Enable database SSL/TLS connections
- [ ] Configure rate limiting on all endpoints
- [ ] Set up monitoring and alerting
- [ ] Enable audit logging for all sensitive operations
- [ ] Configure automated backups
- [ ] Set up intrusion detection system
- [ ] Regular security updates and patches
- [ ] Penetration testing before go-live
- [ ] Staff security training
- [ ] Incident response plan
- [ ] Data privacy compliance (GDPR, CCPA, etc.)

## Critical Security Notes

### 1. Environment Variables
- Never commit `.env.production` to version control
- Use environment variables in production deployment
- Rotate keys regularly (at least every 90 days)

### 2. Database Security
- Use separate database user with minimal permissions
- Enable SSL/TLS for database connections
- Regular database backups with encryption

### 3. Network Security
- Use WAF (Web Application Firewall)
- Configure DDoS protection
- VPN access for administrative functions

### 4. Monitoring
- Set up alerts for failed login attempts
- Monitor for unusual API usage patterns
- Regular security audit logs review
