terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.30"
    }
  }
  required_version = ">= 1.2.0"
}

provider "aws" {
  region = var.region
}

/*
terraform {
  backend "s3" {
    bucket = "lambda_key_rotation"
    key    = "root/workspaces/github/terraform.tfstate"
    region = "us-east-1"
  }
}
*/

variable "repository" {
  type    = string
  default = "test7"
}

variable "environment" {
  type    = string
  default = "MANAGEMENT"
}

variable "region" {
  type    = string
  default = "us-east-1"
}

resource "aws_secretsmanager_secret" "secrets_manager" {
  name = var.repository

  tags = {
    Application = join("-", ["lambda-key-rotation", var.repository])
    Environment = var.environment
    Location    = join("-", ["aws", var.region])
  }
}

resource "aws_secretsmanager_secret_version" "sversion" {
  secret_id     = aws_secretsmanager_secret.secrets_manager.id
  secret_string = <<EOF
    {
    "AWS_ACCESS_KEY_ID": "NULL",
    "AWS_SECRET_ACCESS_KEY": "NULL",
    "GITHUB_TOKEN": "NULL",
    "GITHUB_ORG_REPOSITORY": "NULL"
    }
    EOF
}

resource "aws_iam_user" "repository_iam_user" {
  name = var.repository

  tags = {
    Application = join("-", ["lambda-key-rotation", var.repository])
    Environment = var.environment
    Location    = join("-", ["aws", var.region])
  }
}

resource "aws_iam_role" "lambda_role" {
  name               = "LAMBDA_KEY_ROTATION_ROLE"
  assume_role_policy = <<EOF
    {
    "Version": "2012-10-17",
    "Statement": [
        {
          "Action": "sts:AssumeRole",
          "Principal": {
            "Service": "lambda.amazonaws.com"
          },
          "Effect": "Allow",
          "Sid": ""
        }
      ]
      }
      EOF

  tags = {
    Application = join("-", ["lambda-key-rotation", var.repository])
    Environment = var.environment
    Location    = join("-", ["aws", var.region])
  }
}

resource "aws_iam_policy" "lambda_policy" {
  name        = "aws_iam_policy_for_terraform_aws_lambda_role"
  path        = "/"
  description = "AWS IAM Policy for managing aws lambda role"
  policy = jsonencode({
    "Version" = "2012-10-17"
    "Statement" = [{
      "Action" = [
        "logs:*",
        "iam:*",
        "secretsmanager:*",
        "s3:*",
      ]
      "Effect"   = "Allow"
      "Resource" = "*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "attach_lambda_iam_policy_to_iam_role" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

data "archive_file" "github_webhook_src_zip" {
  type        = "zip"
  source_dir  = "${path.module}/python/"
  output_path = "${path.module}/python/lambda_github_aws_key_rotation.zip"
}

resource "aws_s3_bucket" "github_webhook_bucket" {
  bucket = join("-", ["lambda-code-pipeline", var.repository])
  acl    = "private"

  tags = {
    Application = join("-", ["lambda-key-rotation", var.repository])
    Environment = var.environment
    Location    = join("-", ["aws", var.region])
  }

  depends_on    = [data.archive_file.github_webhook_src_zip]
  force_destroy = true
}

resource "aws_s3_bucket_object" "github_webhook_src" {
  bucket = aws_s3_bucket.github_webhook_bucket.id
  key    = "lambda_github_aws_key_rotation.zip"
  source = data.archive_file.github_webhook_src_zip.output_path
  etag   = filemd5(data.archive_file.github_webhook_src_zip.output_path)
}

resource "aws_lambda_function" "lambda_fx_key_rotation" {

  function_name = join("-", [var.repository, "key-rotation"])
  role          = aws_iam_role.lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.7"

  s3_bucket        = aws_s3_bucket.github_webhook_bucket.id
  s3_key           = aws_s3_bucket_object.github_webhook_src.key
  source_code_hash = data.archive_file.github_webhook_src_zip.output_base64sha256

  tags = {
    Application = join("-", ["lambda-key-rotation", var.repository])
    Environment = var.environment
    Location    = join("-", ["aws", var.region])
  }

  depends_on = [aws_iam_role_policy_attachment.attach_lambda_iam_policy_to_iam_role, aws_s3_bucket_object.github_webhook_src]

}
