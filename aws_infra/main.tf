terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# --- Recursos de Almacenamiento (Bóveda Segura) ---
resource "aws_s3_bucket" "vault" {
  bucket = "dlp-forensic-vault-bucket-${random_id.bucket_suffix.hex}"
}

resource "aws_s3_bucket_public_access_block" "vault_block" {
  bucket                  = aws_s3_bucket.vault.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# --- AWS Cognito User Pool ---
resource "aws_cognito_user_pool" "users" {
  name = "dlp_forensic_users"
}

resource "aws_cognito_user_pool_client" "client" {
  name         = "dlp_frontend_client"
  user_pool_id = aws_cognito_user_pool.users.id
}

# --- Empaquetado Serverless ---
# Asumiremos la preexistencia del entorno layer PyMuPDF compilado acorde a documentation.
resource "aws_lambda_layer_version" "pymupdf_layer" {
  filename            = "pymupdf_layer_amazonlinux.zip"
  layer_name          = "pymupdf_core_dependencies"
  description         = "Dependencias requeridas de fitz y binarios C++"
  compatible_runtimes = ["python3.11"]

  # Exigencia técnica cap 50MB no-blocker si usamos el deployment limit.
}

# Comprimir codigo de lambda en el aire (requerira core copiado o subid explicitamente)
data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/lambda.zip"
  source_dir  = "${path.module}/../" # Esto empaquetara aws_infra y local_app/core
  excludes    = ["venv", ".git", "local_app/vault", "terraform.tfstate*", ".terraform*"]
}

resource "aws_lambda_function" "dlp_processor" {
  function_name    = "dlp_forensic_watermark_processor"
  role             = aws_iam_role.lambda_exec_role.arn
  handler          = "aws_infra.lambda_handler.lambda_handler"
  runtime          = "python3.11"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  # Requsitos funcionales explícitos en memoria/timeout por CPU bounds
  memory_size = 512
  timeout     = 30

  layers = [aws_lambda_layer_version.pymupdf_layer.arn]

  environment {
    variables = {
      S3_BUCKET_NAME = aws_s3_bucket.vault.bucket
    }
  }
}

# --- API Gateway Configuración Segura ---
resource "aws_api_gateway_rest_api" "api" {
  name        = "DLPForensicAPI"
  description = "Pasarela API para validacion forense HTTPS forzado"
}

resource "aws_api_gateway_resource" "upload" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "upload"
}

resource "aws_api_gateway_method" "upload_post" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.upload.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_authorizer" "cognito" {
  name            = "CognitoAuth"
  rest_api_id     = aws_api_gateway_rest_api.api.id
  type            = "COGNITO_USER_POOLS"
  provider_arns   = [aws_cognito_user_pool.users.arn]
  identity_source = "method.request.header.Authorization"
}

resource "aws_api_gateway_integration" "upload_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_resource.upload.id
  http_method             = aws_api_gateway_method.upload_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.dlp_processor.invoke_arn
}

resource "aws_api_gateway_resource" "share" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "share"
}

resource "aws_api_gateway_resource" "share_doc" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.share.id
  path_part   = "{doc_id}"
}

resource "aws_api_gateway_method" "share_get" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.share_doc.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "share_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_resource.share_doc.id
  http_method             = aws_api_gateway_method.share_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.dlp_processor.invoke_arn
}

resource "aws_lambda_permission" "api_gw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.dlp_processor.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
}

# --- Permisos de IAM Lambda ---
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_exec_role" {
  name               = "dlp_lambda_exec_role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "s3_access" {
  statement {
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["${aws_s3_bucket.vault.arn}/vault/*"]
  }
}

resource "aws_iam_role_policy" "s3_policy" {
  name   = "dlp_s3_vault_policy"
  role   = aws_iam_role.lambda_exec_role.id
  policy = data.aws_iam_policy_document.s3_access.json
}
