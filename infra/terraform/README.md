# AWS infrastructure starter

The Terraform module is intentionally not pretending to be production-ready infrastructure. Implement the target topology from `docs/AWS_DEPLOYMENT.md` after choosing a region, networking model, identity approach, and budget. Minimum resources to provision: VPC/private subnets, ECS cluster/services, ECR repositories, RDS PostgreSQL, Secrets Manager, ALB + ACM, CloudWatch logs/alarms, and least-privilege IAM roles.

Do not apply cloud infrastructure without reviewing estimated costs, IAM permissions, network exposure, and teardown procedures.
