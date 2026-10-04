from muxnow.guard import CommandGuard


def test_destructive_commands_flagged():
    guard = CommandGuard()
    destructive_samples = [
        "rm -rf /",
        "rm -rf /var/log/*",
        "mkfs.ext4 /dev/sdb1",
        "dd if=/dev/zero of=/dev/sda bs=1M",
        "iptables -F",
        "echo test > /dev/sda",
        "shutdown -h now",
        "DROP DATABASE production;",
    ]
    for cmd in destructive_samples:
        assessment = guard.assess(cmd)
        assert assessment.level == "destructive", f"Command '{cmd}' should be destructive"
        assert assessment.requires_double_confirm is True


def test_read_only_commands_identified():
    guard = CommandGuard()
    read_only_samples = [
        "ls -la /etc/nginx",
        "cat /etc/os-release",
        "systemctl status postgresql",
        "df -h",
        "docker ps",
        "git log -n 5 --oneline",
    ]
    for cmd in read_only_samples:
        assessment = guard.assess(cmd)
        assert assessment.level == "read-only", f"Command '{cmd}' should be read-only"
        assert assessment.requires_double_confirm is False


def test_write_commands_default():
    guard = CommandGuard()
    write_samples = [
        "mkdir -p /tmp/myfolder",
        "systemctl restart nginx",
        "git commit -m 'feat: add muxnow'",
        "touch /tmp/testfile",
    ]
    for cmd in write_samples:
        assessment = guard.assess(cmd)
        assert assessment.level == "write", f"Command '{cmd}' should be write"
