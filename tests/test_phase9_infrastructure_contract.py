from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_production_minio_compose_isolated_from_test_ports_and_volumes():
    compose = (ROOT / "docker-compose.minio-prod.yml").read_text(encoding="utf-8")
    assert "sermon-minio-prod" in compose
    assert "sermon_minio_prod_data" in compose
    assert "19002" in compose
    assert "19000" not in compose
    assert "minio-test" not in compose
    assert "MINIO_ROOT_PASSWORD:?" in compose
    assert "MINIO_APP_SECRET_KEY:?" in compose


def test_production_minio_template_has_no_real_secret_and_gitignores_runtime_file():
    example = (ROOT / "config" / "minio-prod.env.example").read_text(encoding="utf-8")
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "replace_with" in example
    assert "MINIO_ROOT_PASSWORD=replace_with" in example
    assert "MINIO_APP_SECRET_KEY=replace_with" in example
    assert "config/minio-prod.env" in ignore


def test_production_minio_policy_is_scoped_to_production_prefix():
    policy = (ROOT / "minio-production-app-policy.json").read_text(encoding="utf-8")
    assert "production/*" in policy
    assert '"s3:DeleteObject"' not in policy
