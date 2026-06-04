# DNS is intentionally optional for this assignment deployment.
#
# Leave var.domain_name empty unless Route 53 / custom domain support is
# being added intentionally.

locals {
  dns_enabled = var.domain_name != ""
}
