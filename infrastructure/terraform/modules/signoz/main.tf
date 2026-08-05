resource "aws_instance" "signoz" {
  count         = var.enable_signoz ? 1 : 0
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.large"
  subnet_id     = var.private_subnet_ids[0]
  vpc_security_group_ids = [var.signoz_security_group_id]

  user_data = <<-EOF
              #!/bin/bash
              apt-get update
              apt-get install -y docker.io docker-compose
              systemctl start docker
              systemctl enable docker
              EOF

  tags = {
    Name = "${local.name_prefix}-signoz"
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

output "signoz_instance_id" {
  value = var.enable_signoz ? aws_instance.signoz[0].id : null
}
