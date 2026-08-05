from app.infrastructure.persistence.identity import hash_password, has_perm, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("admin")
    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password("admin", hashed)
    assert not verify_password("wrong", hashed)


def test_admin_has_all_perms():
    user = {
        "roles": [{"code": "admin", "name": "管理员"}],
        "permissions": ["data.read"],
    }
    assert has_perm(user, "user.manage")
    assert has_perm(user, "kb.reindex")
    assert has_perm(user, "kb.manage")


def test_member_cannot_manage_users():
    user = {
        "roles": [{"code": "member", "name": "成员"}],
        "permissions": ["data.read", "data.write", "chat.use"],
    }
    assert has_perm(user, "data.write")
    assert not has_perm(user, "user.manage")
    assert not has_perm(user, "kb.reindex")
    assert not has_perm(user, "kb.manage")
