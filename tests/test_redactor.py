"""Tests for the fail-closed secret redactor (Meets T6 acceptance criteria)."""

import pytest
from muxnow.redactor import SecretRedactor, shannon_entropy


@pytest.fixture
def redactor():
    return SecretRedactor()


def test_private_key_redaction(redactor):
    sample = (
        "Here is the key:\n"
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0Y1234567890abcdefghijklmnopqrstuvwxyz\n"
        "-----END RSA PRIVATE KEY-----\n"
        "done."
    )
    res = redactor.redact(sample)
    assert res.is_safe is True
    assert res.redaction_count >= 1
    assert "MIIEowIBAAKCA" not in res.text
    assert "[REDACTED:PRIVATE_KEY]" in res.text


def test_openssh_key_redaction(redactor):
    sample = (
        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
        "b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAACFwAAAAdzc2gtcn\n"
        "-----END OPENSSH PRIVATE KEY-----"
    )
    res = redactor.redact(sample)
    assert res.is_safe is True
    assert "b3BlbnNza" not in res.text
    assert "[REDACTED:OPENSSH_PRIVATE_KEY]" in res.text


def test_bearer_token_redaction(redactor):
    sample = "curl -H 'Authorization: Bearer secret_bearer_token_1234567890' https://api.local"
    res = redactor.redact(sample)
    assert res.is_safe is True
    assert "secret_bearer_token" not in res.text
    assert "[REDACTED:BEARER_TOKEN]" in res.text


def test_jwt_token_redaction(redactor):
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    sample = f"Token is: {jwt}"
    res = redactor.redact(sample)
    assert res.is_safe is True
    assert jwt not in res.text
    assert "[REDACTED:JWT_TOKEN]" in res.text


def test_aws_access_key_redaction(redactor):
    sample = "export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
    res = redactor.redact(sample)
    assert res.is_safe is True
    assert "AKIAIOSFODNN7EXAMPLE" not in res.text
    assert "[REDACTED:AWS_ACCESS_KEY]" in res.text


def test_github_token_redaction(redactor):
    sample = "clone https://ghp_abcdefghijklmnopqrstuvwxyz0123456789@github.com/repo"
    res = redactor.redact(sample)
    assert res.is_safe is True
    assert "ghp_abcdef" not in res.text
    assert "[REDACTED:GITHUB_TOKEN]" in res.text


def test_gitlab_token_redaction(redactor):
    sample = "curl --header 'PRIVATE-TOKEN: glpat-abcdefghijklmnopqrstuvwxyz01'"
    res = redactor.redact(sample)
    assert res.is_safe is True
    assert "glpat-abcdef" not in res.text
    assert "[REDACTED:GITLAB_TOKEN]" in res.text


def test_slack_token_redaction(redactor):
    sample = "SLACK_TOKEN=xoxb-123456789012-1234567890123-abcdefghijklmnopqrstuvwx"
    res = redactor.redact(sample)
    assert res.is_safe is True
    assert "xoxb-12345678" not in res.text
    assert "[REDACTED:SLACK_TOKEN]" in res.text


def test_telegram_token_redaction(redactor):
    sample = "https://api.telegram.org/bot123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ123456789/sendMessage"
    res = redactor.redact(sample)
    assert res.is_safe is True
    assert "123456789:ABCdef" not in res.text
    assert "[REDACTED:TELEGRAM_TOKEN]" in res.text


def test_password_assignments(redactor):
    probes = [
        ("password=MySuperSecret99!", "MySuperSecret99!"),
        ("password: 'AnotherSecretPass'", "AnotherSecretPass"),
        ("api_key = super_duper_api_key_value", "super_duper_api_key_value"),
        ("auth_token: TokenSecret123", "TokenSecret123"),
    ]
    for probe, secret in probes:
        res = redactor.redact(probe)
        assert res.is_safe is True
        assert secret not in res.text
        assert "[REDACTED:PASSWORD_ASSIGNMENT]" in res.text


def test_cli_password_flags(redactor):
    sample = "mysql -u root --password='DatabasePass123' db_production"
    res = redactor.redact(sample)
    assert res.is_safe is True
    assert "DatabasePass123" not in res.text
    assert "[REDACTED:CLI_PASSWORD_FLAG]" in res.text


def test_basic_auth_url(redactor):
    sample = "curl https://admin:super_secret_pw@service.internal/api"
    res = redactor.redact(sample)
    assert res.is_safe is True
    assert "super_secret_pw" not in res.text
    assert "[REDACTED:PASSWORD]" in res.text

    sample_curl_flag = "curl -u admin:super_secret_pw https://service.internal/api"
    res_flag = redactor.redact(sample_curl_flag)
    assert res_flag.is_safe is True
    assert "super_secret_pw" not in res_flag.text
    assert "[REDACTED:PASSWORD]" in res_flag.text


def test_high_entropy_secret_redaction(redactor):
    # Base64 high entropy token 32+ chars
    high_entropy = "4kL9zX2pQ8mR5tV1wY7aB3cD6eF0gH2j"
    sample = f"token_cache_val={high_entropy}"
    res = redactor.redact(sample)
    assert res.is_safe is True
    assert high_entropy not in res.text


def test_false_positive_preservation(redactor):
    # Standard Linux commands and outputs must remain completely untouched
    normal_text = (
        "root@host:~# systemctl status nginx\n"
        "● nginx.service - A high performance web server and a reverse proxy server\n"
        "   Loaded: loaded (/lib/systemd/system/nginx.service; enabled; vendor preset: enabled)\n"
        "   Active: failed (Result: exit-code) since Sun 2026-10-04 11:20:00 UTC\n"
        "   Process: 1234 ExecStartPre=/usr/sbin/nginx -t (code=exited, status=1/FAILURE)"
    )
    res = redactor.redact(normal_text)
    assert res.is_safe is True
    assert res.redaction_count == 0
    assert res.text == normal_text


def test_fail_closed_on_unscrubbed_private_key():
    redactor = SecretRedactor(fail_closed=True)
    # Simulate an incomplete/broken private key block
    malformed = "-----BEGIN SOMETHING PRIVATE KEY----- corrupted data"
    res = redactor.redact(malformed)
    # The safety check triggers fail-closed
    assert res.is_safe is False
    assert res.text == ""
    assert "Fail-closed trip" in res.error
