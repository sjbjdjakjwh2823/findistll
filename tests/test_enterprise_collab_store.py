from app.db.client import InMemoryDB
from app.core.tenant_context import set_tenant_id, clear_tenant_id
from app.services.enterprise_collab import EnterpriseCollabStore, TenantPipelineManager


def test_store_friend_team_transfer_pipeline():
    db = InMemoryDB()
    set_tenant_id("t1")
    try:
        store = EnterpriseCollabStore(db)

        req = store.request_contact(requester_user_id="alice", target_user_id="bob")
        assert req["status"] == "pending"
        accepted = store.accept_contact(current_user_id="bob", contact_id=req["id"])
        assert accepted["status"] == "accepted"
        assert store.are_friends(user_a="alice", user_b="bob")

        team = store.create_team(owner_user_id="alice", name="Risk Team")
        store.add_team_member(actor_user_id="alice", team_id=team["id"], user_id="bob", role="member")
        space = store.create_space(actor_user_id="alice", space_type="team", name="Shared", team_id=team["id"])
        file_row = store.register_file(actor_user_id="alice", space_id=space["id"], doc_id="doc-1", visibility="team")
        assert store.can_read_file(user_id="bob", file_id=file_row["id"])

        transfer = store.send_transfer(sender_user_id="alice", receiver_user_id="bob", file_id=file_row["id"], message="check")
        inbox = store.list_inbox(user_id="bob")
        assert any(x["id"] == transfer["id"] for x in inbox)
        ack = store.ack_transfer(user_id="bob", transfer_id=transfer["id"], status="accepted")
        assert ack["status"] == "accepted"

        manager = TenantPipelineManager(db)
        job = manager.submit(user_id="alice", job_type="rag", flow="interactive", input_ref={"query": "macro risk"})
        assert job["status"] == "pending"
        updated = manager.store.update_pipeline_job_status(
            actor_user_id="alice",
            job_id=job["id"],
            status="completed",
            output_ref={"ok": True},
        )
        assert updated.get("status") == "completed"
        status = manager.status(user_id="alice")
        assert status["job_counts_by_status"].get("completed", 0) >= 1
        assert status["profile"]["rag_profile_json"]["engine"] == "shared-rag"
    finally:
        clear_tenant_id()


def test_store_tenant_isolation():
    db = InMemoryDB()
    set_tenant_id("t1")
    try:
        store_t1 = EnterpriseCollabStore(db)
        req = store_t1.request_contact(requester_user_id="alice", target_user_id="bob")
        assert req["status"] == "pending"
    finally:
        clear_tenant_id()

    set_tenant_id("t2")
    try:
        store_t2 = EnterpriseCollabStore(db)
        rows = store_t2.list_contacts(current_user_id="bob")
        assert rows == []
    finally:
        clear_tenant_id()
