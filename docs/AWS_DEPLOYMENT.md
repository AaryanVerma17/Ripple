# AWS deployment guide (MVP)

Recommended low-ops topology:
- Frontend: AWS Amplify Hosting or ECS/Fargate.
- API: ECS Fargate service behind an Application Load Balancer.
- Database: Amazon RDS for PostgreSQL.
- Uploaded documents (when implemented): private S3 bucket with SSE-KMS.
- Secrets: AWS Secrets Manager.
- Logs/metrics: CloudWatch.
- DNS/TLS: Route 53 + ACM.
- Container registry: ECR.

## Important caveat
The included Docker Compose setup is the quickest reproducible demo. The API currently uses a JSON-file audit store to keep local setup simple; that store is not safe for multiple replicas and is not a substitute for RDS. Before ECS production deployment, replace `app/store.py` with a PostgreSQL-backed repository, create migrations, and configure health checks and database connectivity.

## Build and run locally first
```bash
cp .env.example .env
docker compose up --build
```

## ECR / ECS outline
1. Create an ECR repository for `ripple-api` and `ripple-web`.
2. Build and push immutable tagged images from CI.
3. Create an ECS cluster and Fargate task definitions in private subnets.
4. Put the API behind an ALB; allow ingress only from the ALB security group.
5. Put RDS in private subnets, require TLS, and allow database ingress only from the API task security group.
6. Store the Nebius key in Secrets Manager and reference it from the API task definition. Do not bake it into the image.
7. Configure the frontend's public API URL at build time and use HTTPS.
8. Add ALB health checks to `/health`; configure CloudWatch logs, alarms, and autoscaling.
9. Set a restrictive CORS allowlist, rate limits, and authentication before public multi-user use.
10. Test the deployed model call and verify no secret appears in browser network requests or logs.

## Minimal cost / hackathon option
Use a single API container and hosted frontend for the demo, but understand persistence and availability limits. Do not expose an unauthenticated API containing private engineering data.
