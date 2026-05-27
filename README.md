# FIT5225_Ass2_AussieEcoLen

## Installation Guide
1. Install aws cli:
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```
2. install npm for frontend development (Maybe Optional?)
3. Launch AWS Academy Learner Lab -> Start Lab -> AWS Detail -> copy everything into `~/.aws/credentials`. This step will let terraform to provision IaC in the AWS Academy Learner Lab.

## Frontend Start Command
```
# install dependencies
npm install

# run development server
npm run dev
```

Create an .env file under ./frontend/ with these environment variables:
```
export VITE_COGNITO_USER_POOL_ID="<Actual User Pool ID>"
export VITE_COGNITO_USER_POOL_CLIENT_ID="<Actual Client ID>"
export VITE_API_URL="<Actual API Gateway API URL>"
```
