import pytest
from fastapi import UploadFile
from app.services.convert_audio_service import convert_audio
import io


@pytest.fixture
def mock_wav_file():
    return UploadFile(
        filename="test.wav",
        file=io.BytesIO(b"RIFF....WAVEfmt "),  # Minimal WAV header
        content_type="audio/wav",
    )


@pytest.fixture
def mock_mp3_file():
    return UploadFile(
        filename="test.mp3",
        file=io.BytesIO(b"ID3"),  # Minimal MP3 header
        content_type="audio/mpeg",
    )


@pytest.fixture
def mock_invalid_file():
    return UploadFile(
        filename="test.txt",
        file=io.BytesIO(b"Invalid content"),
        content_type="text/plain",
    )


def test_convert_audio_to_wav(mock_wav_file):
    converted_file = convert_audio(mock_wav_file)
    assert converted_file.filename.endswith(".wav")
    assert converted_file.content_type == "audio/wav"


def test_convert_audio_to_mp3(mock_mp3_file):
    converted_file = convert_audio(mock_mp3_file)
    assert converted_file.filename.endswith(".mp3")
    assert converted_file.content_type == "audio/mpeg"


def test_convert_invalid_file(mock_invalid_file):
    with pytest.raises(Exception):  # Replace with specific exception if applicable
        convert_audio(mock_invalid_file)


def test_original_file_cleanup(mock_wav_file, tmp_path, monkeypatch):
    temp_files = []

    def mock_named_temporary_file(*args, **kwargs):
        temp_file = tmp_path / f"tempfile_{len(temp_files)}"
        temp_files.append(temp_file)
        return open(temp_file, "wb")

    monkeypatch.setattr("tempfile.NamedTemporaryFile", mock_named_temporary_file)

    convert_audio(mock_wav_file)

    for temp_file in temp_files:
        assert not temp_file.exists()


def test_output_file_cleanup(mock_wav_file, tmp_path, monkeypatch):
    temp_files = []

    def mock_named_temporary_file(*args, **kwargs):
        temp_file = tmp_path / f"tempfile_{len(temp_files)}"
        temp_files.append(temp_file)
        return open(temp_file, "wb")

    monkeypatch.setattr("tempfile.NamedTemporaryFile", mock_named_temporary_file)

    converted_file = convert_audio(mock_wav_file)
    converted_file.file.close()  # Ensure file is closed before cleanup

    for temp_file in temp_files[:-1]:  # Input files should be cleaned up
        assert not temp_file.exists()

    assert temp_files[-1].exists()  # Output file should still exist
