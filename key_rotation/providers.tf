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

terraform {
  backend "s3" {
    bucket = "us-east1-tpatch-terraform"
    key    = "root/workspaces/github/terraform.tfstate"
    region = "us-east-1"
  }
}