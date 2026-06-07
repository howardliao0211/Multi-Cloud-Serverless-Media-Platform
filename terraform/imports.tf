import {
  to = module.lambda_functions["query_file"].aws_lambda_function.this
  id = "query_file"
}

import {
  to = module.lambda_functions["tag_image"].aws_lambda_function.this
  id = "tag_image"
}

import {
  to = module.lambda_functions["tag_video"].aws_lambda_function.this
  id = "tag_video"
}
