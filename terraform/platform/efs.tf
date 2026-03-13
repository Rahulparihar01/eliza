resource "aws_efs_file_system" "volumes" {
  for_each         = toset(["postgres-data", "redis-data", "neo4j-data", "neo4j-logs", "elasticsearch-data"])
  encrypted        = true
  performance_mode = "generalPurpose"
  tags = { Name = "${var.project}-${each.key}" }
}

resource "aws_efs_mount_target" "volumes" {
  for_each = {
    for combo in flatten([
      for name, fs in aws_efs_file_system.volumes : [
        for idx, subnet in aws_subnet.private : {
          key       = "${name}-${idx}"
          fs_id     = fs.id
          subnet_id = subnet.id
        }
      ]
    ]) : combo.key => combo
  }
  file_system_id  = each.value.fs_id
  subnet_id       = each.value.subnet_id
  security_groups = [aws_security_group.efs.id]
}

# Access points per volume
resource "aws_efs_access_point" "volumes" {
  for_each       = aws_efs_file_system.volumes
  file_system_id = each.value.id
  posix_user {
    uid = 0
    gid = 0
  }
  root_directory {
    path = "/"
    creation_info {
      owner_uid    = 0
      owner_gid    = 0
      permissions  = "755"
    }
  }
  tags = { Name = "${var.project}-ap-${each.key}" }
}