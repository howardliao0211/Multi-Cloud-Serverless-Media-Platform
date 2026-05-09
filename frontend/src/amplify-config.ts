import { Amplify } from "aws-amplify";

const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID as string;
const userPoolClientId = import.meta.env.VITE_COGNITO_USER_POOL_CLIENT_ID as string;

if (!userPoolId || !userPoolClientId) {
  throw new Error("Missing Cognito environment variables.");
}

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId,
      userPoolClientId,
      loginWith: {
        email: true,
      },
    },
  },
});