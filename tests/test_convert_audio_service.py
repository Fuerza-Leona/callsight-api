import pytest
from app.services.convert_audio_service import convert_audio, ConvertedUploadFile
import io
from unittest.mock import patch
import subprocess
import os
import tempfile  # Import tempfile


@pytest.fixture
def mock_wav_file():
    return ConvertedUploadFile(
        filename="test.wav",
        file=io.BytesIO(b"RIFF....WAVEfmt "),  # Minimal WAV header
        content_type="audio/wav",
    )


@pytest.fixture
def mock_mp3_file():
    return ConvertedUploadFile(
        filename="test.mp3",
        file=io.BytesIO(b"ID3"),  # Minimal MP3 header
        content_type="audio/mpeg",
    )


@pytest.fixture
def mock_invalid_file():
    return ConvertedUploadFile(
        filename="test.txt",
        file=io.BytesIO(b"Invalid content"),
        content_type="text/plain",
    )


@patch("subprocess.run")
def test_convert_audio_to_wav(mock_subprocess_run, mock_wav_file):
    def side_effect(*args, **kwargs):
        output_path = args[0][-1]
        open(output_path, "a").close()
        return None

    mock_subprocess_run.side_effect = side_effect
    converted_file = convert_audio(mock_wav_file)
    assert converted_file.filename.endswith(".wav")
    assert converted_file.content_type == "audio/wav"
    if os.path.exists(converted_file.file.name):
        converted_file.file.close()


@patch("subprocess.run")
def test_convert_audio_to_mp3(mock_subprocess_run, mock_mp3_file):
    def side_effect(*args, **kwargs):
        output_path = args[0][-1]
        if output_path.endswith(".wav"):
            raise subprocess.CalledProcessError(1, "ffmpeg")
        elif output_path.endswith(".mp3"):
            open(output_path, "a").close()
            return None
        raise ValueError("Unexpected output path in mock")

    mock_subprocess_run.side_effect = side_effect
    converted_file = convert_audio(mock_mp3_file)
    assert converted_file.filename.endswith(".mp3")
    assert converted_file.content_type == "audio/mpeg"
    if os.path.exists(converted_file.file.name):
        converted_file.file.close()


@patch("subprocess.run")
def test_convert_invalid_file(mock_subprocess_run, mock_invalid_file):
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, "ffmpeg")
    with pytest.raises(subprocess.CalledProcessError):
        convert_audio(mock_invalid_file)


@patch("subprocess.run")
def test_original_file_cleanup(
    mock_subprocess_run, mock_wav_file, tmp_path, monkeypatch
):
    def side_effect(*args, **kwargs):
        output_path = args[0][-1]
        open(output_path, "a").close()
        return None

    mock_subprocess_run.side_effect = side_effect
    temp_files = []
    output_file_path = None

    original_named_temp = tempfile.NamedTemporaryFile

    def mock_named_temporary_file(*args, **kwargs):
        temp_file_obj = original_named_temp(
            delete=False, dir=tmp_path, suffix=kwargs.get("suffix", "")
        )
        temp_files.append(temp_file_obj.name)
        if kwargs.get("suffix") is None:
            nonlocal output_file_path
            output_file_path = temp_file_obj.name + ".wav"
        return temp_file_obj

    monkeypatch.setattr("tempfile.NamedTemporaryFile", mock_named_temporary_file)

    converted_file = convert_audio(mock_wav_file)

    assert len(temp_files) >= 2
    input_temp_path = temp_files[0]
    assert not os.path.exists(input_temp_path)

    if (
        converted_file
        and hasattr(converted_file, "file")
        and hasattr(converted_file.file, "name")
    ):
        if os.path.exists(converted_file.file.name):
            converted_file.file.close()


@patch("subprocess.run")
def test_output_file_cleanup(mock_subprocess_run, mock_wav_file, tmp_path, monkeypatch):
    def side_effect(*args, **kwargs):
        output_path = args[0][-1]
        open(output_path, "a").close()
        return None

    mock_subprocess_run.side_effect = side_effect
    temp_files = []
    output_file_path_actual = None

    original_named_temp = tempfile.NamedTemporaryFile

    def mock_named_temporary_file(*args, **kwargs):
        temp_file_obj = original_named_temp(
            delete=False, dir=tmp_path, suffix=kwargs.get("suffix", "")
        )
        temp_files.append(temp_file_obj.name)
        if kwargs.get("suffix") is None:
            nonlocal output_file_path_actual
            output_file_path_actual = temp_file_obj.name + ".wav"
        return temp_file_obj

    monkeypatch.setattr("tempfile.NamedTemporaryFile", mock_named_temporary_file)

    converted_file = convert_audio(mock_wav_file)

    assert len(temp_files) >= 2
    input_temp_path = temp_files[0]
    assert not os.path.exists(input_temp_path)

    assert output_file_path_actual is not None
    assert os.path.exists(output_file_path_actual)
    assert converted_file.file.name == output_file_path_actual

    converted_file.file.close()
    os.remove(converted_file.file.name)
    assert not os.path.exists(converted_file.file.name)
