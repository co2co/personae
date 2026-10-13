"""剧本级导入 / 导出（统一 JSON 模板）测试（v0.28.3）。

一个剧本 = 一本世界书 + 该剧本全部角色。导出/恢复走统一模板（store.export_drama /
store.import_drama），模板形状：
    {schema, schema_version, drama, exported_at, exported_by, world{name,entries}, characters[]}

覆盖：
  1. store 层：导出形状正确（world 原样 + 角色按 world 归属收录 + 扩展字段保留）。
  2. store 层：导入精确还原（世界书整份覆盖、角色 world 对齐目标剧本名、模板外多余卡清理、
     其它剧本不碰）。
  3. store 层：错误分支（空名 / 非 dict / 缺字段 / 剧本不存在 / 旧版无 schema 模板）。
  4. HTTP 层：/api/drama/<name>/export 与 /api/drama/<name>/import 路由冒烟 + 往返。

全部走隔离的 store.DATA_DIR（临时目录），不碰真实 data/、不调任何 LLM。
conftest 的 _isolate_session_dir 只隔离 memory.SESS_DIR，store 数据目录须本文件自隔离。
"""
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import store  # noqa: E402
import app as engine_app  # noqa: E402


@pytest.fixture
def data(tmp_path, monkeypatch):
    """把 store.DATA_DIR 指到临时目录并清缓存，磁盘读写自洽、不污染真实 data/。"""
    d = tmp_path / "data"
    (d / "characters").mkdir(parents=True)
    (d / "worlds").mkdir(parents=True)
    monkeypatch.setattr(store, "DATA_DIR", d)
    monkeypatch.setattr(store, "EXAMPLES_DIR", d / "examples")
    store._cache.clear()
    yield d
    store._cache.clear()


@pytest.fixture
def client(data):
    """test_client + 真实 store（DATA_DIR 已隔离）：路由走真实磁盘逻辑，无 LLM。"""
    return engine_app.app.test_client()


def _seed():
    """建两个剧本的桩数据：甲剧本 2 角色（甲角2 带扩展字段）+ 乙剧本 1 角色。

    写的是隔离后的全局 store.DATA_DIR，故无需传目录。
    """
    store.save_world("甲", [{"keys": ["x"], "content": "甲的设定"}])
    store.save_world("乙", [{"keys": ["y"], "content": "乙的设定"}])
    store.save_card("甲角", {"name": "甲角", "world": "甲", "core_desire": "d"})
    store.save_card("甲角2", {"name": "甲角2", "world": "甲", "core_desire": "d2",
                              "extensions": {"avatar": "a.png"}})  # 扩展字段须保留
    store.save_card("乙角", {"name": "乙角", "world": "乙", "core_desire": "d3"})


# ---------------------------------------------------------------------------
# 1. store 层：导出
# ---------------------------------------------------------------------------

def test_export_shape_and_membership(data):
    _seed()
    tpl = store.export_drama("甲")
    assert tpl["schema"] == store.SCHEMA_ID
    assert tpl["schema_version"] == store.SCHEMA_VERSION
    assert tpl["drama"] == "甲"
    assert tpl["world"]["name"] == "甲"
    # 角色只收录 world==甲 的两张，乙角不在内；按名升序
    assert [c["name"] for c in tpl["characters"]] == ["甲角", "甲角2"]
    # 扩展字段随卡原样保留
    assert next(c for c in tpl["characters"] if c["name"] == "甲角2")["extensions"] == {"avatar": "a.png"}
    # save_world 新建会播种一条「亲密描写标准」，故 world 条目含标准条
    assert "亲密描写标准" in [e.get("name") for e in tpl["world"]["entries"]]


def test_export_missing_drama_returns_none(data):
    _seed()
    assert store.export_drama("不存在") is None


def test_export_empty_name_raises(data):
    _seed()
    with pytest.raises(ValueError):
        store.export_drama("   ")


# ---------------------------------------------------------------------------
# 2. store 层：导入（精确还原 + world 对齐 + 模板外清理 + 跨剧本不碰）
# ---------------------------------------------------------------------------

def test_import_restores_world_and_characters(data):
    _seed()
    tpl = store.export_drama("甲")
    # 删掉甲，模拟「剧本已丢、要用备份恢复」
    store.delete_world("甲")
    store.delete_card("甲角")
    store.delete_card("甲角2")
    res = store.import_drama("甲", tpl)
    assert res["ok"] is True and res["name"] == "甲"
    # 世界书恢复（含甲的设定）
    assert any(e["content"] == "甲的设定" for e in store.load_world("甲"))
    # 角色恢复、扩展字段保留
    assert set(store.list_characters()) == {"甲角", "甲角2", "乙角"}
    assert store.load_card("甲角2")["extensions"] == {"avatar": "a.png"}
    assert res["imported"] == ["甲角", "甲角2"]
    # 乙剧本未受影响
    assert store.load_card("乙角")["world"] == "乙"


def test_import_aligns_world_to_target_name(data):
    """恢复成另一个剧本名：模板内 world 与角色卡 world 一律对齐目标名。"""
    _seed()
    tpl = store.export_drama("甲")
    res = store.import_drama("乙", tpl)  # 把甲的内容恢复成「乙」
    assert res["ok"] is True and res["name"] == "乙"
    # 乙的世界书被甲的设定覆盖
    assert any(e["content"] == "甲的设定" for e in store.load_world("乙"))
    # 原乙角不在模板里 → 被清理；甲角/甲角2 的 world 对齐成「乙」
    assert "乙角" in res["deleted"]
    assert store.load_card("甲角")["world"] == "乙"
    assert store.load_card("甲角2")["world"] == "乙"
    assert set(store.list_characters()) == {"甲角", "甲角2"}
    # 源剧本「甲」不受影响（导入是恢复快照到目标，不是把甲搬去乙）
    assert store.load_world_raw("甲") is not None
    assert any(e["content"] == "甲的设定" for e in store.load_world("甲"))


def test_import_removes_stale_cards_not_in_template(data):
    """模板没列、但当前归属目标剧本的多余卡，导入时删除（精确还原，不留残卡）。"""
    _seed()
    store.save_card("甲角残", {"name": "甲角残", "world": "甲"})  # 当前多余卡
    tpl = store.export_drama("甲")
    tpl["characters"] = [c for c in tpl["characters"] if c["name"] != "甲角残"]
    res = store.import_drama("甲", tpl)
    assert "甲角残" in res["deleted"]
    assert set(store.list_characters()) == {"甲角", "甲角2", "乙角"}


def test_import_does_not_touch_other_dramas(data):
    """导入甲时，乙剧本的卡一律不碰。"""
    _seed()
    tpl = store.export_drama("甲")
    res = store.import_drama("甲", tpl)
    assert "乙角" not in res["deleted"]
    assert store.load_card("乙角")["world"] == "乙"


# ---------------------------------------------------------------------------
# 3. store 层：导入错误分支
# ---------------------------------------------------------------------------

def test_import_empty_name_raises(data):
    _seed()
    with pytest.raises(ValueError):
        store.import_drama("", {"world": {"name": "x", "entries": []}})


def test_import_non_dict_raises(data):
    _seed()
    with pytest.raises(ValueError):
        store.import_drama("甲", [1, 2, 3])


def test_import_missing_fields_raises(data):
    _seed()
    with pytest.raises(ValueError):
        store.import_drama("甲", {"foo": "bar"})  # 无 world / characters


def test_import_accepts_legacy_template_without_schema(data):
    """兼容旧版无 schema 字段的裸 {world, characters} 模板。"""
    _seed()
    legacy = {"world": {"name": "甲", "entries": store.load_world("甲")},
              "characters": [{"name": "甲角", "world": "甲", "core_desire": "d"}]}
    res = store.import_drama("甲", legacy)
    assert res["ok"] is True
    assert set(store.list_characters()) == {"甲角", "乙角"}  # 甲角2 不在旧模板 → 被清


# ---------------------------------------------------------------------------
# 4. HTTP 层：路由冒烟 + 往返
# ---------------------------------------------------------------------------

def test_export_endpoint_200(client):
    _seed()
    r = client.get("/api/drama/%E7%94%B2/export")  # 甲
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["schema"] == store.SCHEMA_ID
    assert d["drama"] == "甲"
    assert len(d["characters"]) == 2


def test_export_endpoint_missing_404(client):
    r = client.get("/api/drama/%E4%B8%8D%E5%AD%98%E5%9C%A8/export")  # 不存在
    assert r.status_code == 404


def test_import_endpoint_roundtrip(client):
    _seed()
    tpl = client.get("/api/drama/%E7%94%B2/export").get_json()  # 甲
    # 删甲 → 用同一模板 POST 恢复
    store.delete_world("甲")
    store.delete_card("甲角"); store.delete_card("甲角2")
    r = client.post("/api/drama/%E7%94%B2/import", json=tpl)  # 甲
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["ok"] is True and d["name"] == "甲"
    assert set(store.list_characters()) == {"甲角", "甲角2", "乙角"}


def test_import_endpoint_bad_body_400(client):
    r = client.post("/api/drama/%E7%94%B2/import", data="not json",
                    content_type="application/json")
    assert r.status_code == 400


def test_import_endpoint_missing_fields_400(client):
    r = client.post("/api/drama/%E7%94%B2/import", json={"foo": "bar"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# 5. store 层 + HTTP 层：删除剧本（世界书 + 全部角色卡，一并清掉）
# ---------------------------------------------------------------------------

def test_delete_drama_removes_world_and_all_cards(data):
    """删剧本 = 世界书 + 该剧本全部角色卡，其它剧本不碰。"""
    _seed()
    res = store.delete_drama("甲")
    assert res["ok"] is True and res["name"] == "甲"
    assert res["world_removed"] is True
    assert sorted(res["characters_deleted"]) == ["甲角", "甲角2"]
    # 世界书没了
    assert store.load_world_raw("甲") is None
    # 甲的两张卡全删，乙角保留（world==乙，不碰）
    assert set(store.list_characters()) == {"乙角"}
    assert store.load_card("乙角")["world"] == "乙"


def test_delete_drama_missing_returns_none(data):
    """世界书与角色都不存在 → 返回 None（路由据此回 404）。"""
    _seed()
    assert store.delete_drama("不存在") is None


def test_delete_drama_empty_name_raises(data):
    _seed()
    with pytest.raises(ValueError):
        store.delete_drama("   ")


def test_delete_drama_orphan_world_only(data):
    """只有世界书、没有归属角色 → 删世界书，characters_deleted 为空。"""
    store.save_world("甲", [{"keys": ["x"], "content": "甲的设定"}])
    res = store.delete_drama("甲")
    assert res["ok"] is True and res["world_removed"] is True
    assert res["characters_deleted"] == []


def test_delete_drama_endpoint_removes_world_and_cards(client):
    """HTTP：DELETE /api/drama/<name>/delete 一并清掉世界书 + 角色。"""
    _seed()
    r = client.delete("/api/drama/%E7%94%B2/delete")  # 甲
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["ok"] is True and d["name"] == "甲"
    assert d["world_removed"] is True
    assert sorted(d["characters_deleted"]) == ["甲角", "甲角2"]
    assert store.load_world_raw("甲") is None
    assert set(store.list_characters()) == {"乙角"}


def test_delete_drama_endpoint_missing_404(client):
    _seed()
    r = client.delete("/api/drama/%E4%B8%8D%E5%AD%98%E5%9C%A8/delete")  # 不存在
    assert r.status_code == 404
