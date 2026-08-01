"""Integration coverage for ASR results through the shared ingestion batch."""

from router.ingestion.asr import ASRResult
from router.ingestion.pipeline import run_media_ingestion

from ingestion_fakes import FakeASRClient, FakeOCRClient


def test_batch_ingestion_routes_a_voice_transcript_through_normalized_text(
    load_fixture_bundle, fixtures_dir
):
    """Voice and native-text rows coexist in the one normalized-message dictionary."""
    bundle = load_fixture_bundle("dataset_valid")
    voice_row = bundle.messages.iloc[0].copy()
    voice_row["message_id"] = "voice_message"
    voice_row["media_type"] = "voice"
    voice_row["media_id"] = "vn_test_001"
    voice_row["message_text"] = ""
    bundle.messages.loc[0] = voice_row
    client = FakeASRClient(ASRResult("Transcript from voice", 0.77, False, None))

    normalized = run_media_ingestion(
        bundle, fixtures_dir / "dataset_valid", FakeOCRClient(), client
    )

    assert normalized["voice_message"].normalized_text == "Transcript from voice"
    assert normalized["voice_message"].media_category == "voice_note"
    assert normalized["msg_test_002"].normalized_text == "Special offer just for you!"
    assert len(client.calls) == 1
