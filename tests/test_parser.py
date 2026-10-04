"""Tests for the OSC 133 block parser and ANSI sequence stripper (Meets T8)."""

from muxnow.parser import BlockParser, strip_ansi


def test_strip_ansi_color_and_escapes():
    colored = "\x1b[31mError:\x1b[0m File not found\x1b[1m in line 42\x1b[0m\r\n"
    assert strip_ansi(colored) == "Error: File not found in line 42\n"


def test_osc_133_block_parsing_success():
    parser = BlockParser()
    # Feed chunk with OSC 133 prompt (A), command (C), and exit (D;0)
    stream = (
        "\x1b]133;A\x07"
        "systemctl status nginx"
        "\x1b]133;C\x07"
        "Active: active (running)\n"
        "\x1b]133;D;0\x07"
    )
    blocks = parser.feed(stream)
    assert len(blocks) == 1
    b = blocks[0]
    assert b.command == "systemctl status nginx"
    assert b.output == "Active: active (running)"
    assert b.exit_code == 0
    assert b.is_failed is False


def test_osc_133_block_parsing_error_exit_code():
    parser = BlockParser()
    stream = (
        "\x1b]133;A\x07"
        "ls /nonexistent_directory"
        "\x1b]133;C\x07"
        "ls: cannot access '/nonexistent_directory': No such file or directory\n"
        "\x1b]133;D;2\x07"
    )
    blocks = parser.feed(stream)
    assert len(blocks) == 1
    b = blocks[0]
    assert b.command == "ls /nonexistent_directory"
    assert "No such file or directory" in b.output
    assert b.exit_code == 2
    assert b.is_failed is True


def test_plain_stream_fallback():
    parser = BlockParser()
    sample = (
        "root@host:~# uname -a\n"
        "Linux test-host 6.1.0-25-amd64 #1 SMP PREEMPT_DYNAMIC Debian\n"
        "root@host:~# df -h\n"
        "Filesystem      Size  Used Avail Use% Mounted on\n"
        "/dev/sda1        50G   12G   36G  25% /\n"
    )
    blocks = parser.parse_plain_stream(sample)
    assert len(blocks) >= 2
    assert blocks[0].command == "uname -a"
    assert "Linux test-host" in blocks[0].output
    assert blocks[1].command == "df -h"
    assert "Filesystem" in blocks[1].output
