import subprocess
import tempfile
import os
from fastapi import UploadFile
from typing import IO
from starlette.datastructures import UploadFile as StarletteUploadFile


class ConvertedUploadFile(StarletteUploadFile):
    def __init__(self, filename: str, file: IO[bytes], content_type: str):
        super().__init__(filename=filename, file=file)
        self._custom_content_type = content_type

    @property
    def content_type(self) -> str:
        return self._custom_content_type


""" def convert_audio(original_file: UploadFile) -> UploadFile:
    # Write original to temp
    suffix = (
        "." + original_file.filename.split(".")[-1]
        if "." in original_file.filename
        else ""
    )
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as input_temp:
        input_temp.write(original_file.file.read())
        input_path = input_temp.name

    base_output = tempfile.NamedTemporaryFile(delete=False).name

    # Try .wav first, if it doesn't work, try .mp3
    try:
        output_path = base_output + ".wav"
        subprocess.run(
            ["ffmpeg", "-y", "-i", input_path, output_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        filename = os.path.basename(output_path)
        mime = "audio/wav"
    except subprocess.CalledProcessError:
        output_path = base_output + ".mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-i", input_path, output_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        filename = os.path.basename(output_path)
        mime = "audio/mpeg"

    # Read converted file into BytesIO and wrap it as UploadFile
    file_like = open(output_path, "rb")
    upload_file = ConvertedUploadFile(
        filename=filename, file=file_like, content_type=mime
    )

    # Clean up input file
    os.remove(input_path)
    # output_path is still being used — don't delete yet

    return upload_file
 """

def convert_audio(original_file: UploadFile) -> UploadFile:
    suffix = (
        "." + original_file.filename.split(".")[-1]
        if "." in original_file.filename
        else ""
    )
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as input_temp:
        input_temp.write(original_file.file.read())
        input_path = input_temp.name

    base_output = tempfile.NamedTemporaryFile(delete=False).name
    output_path = base_output + ".mp3"

    subprocess.run(
        ["ffmpeg", "-y", "-i", input_path, "-b:a", "64k", output_path],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    filename = os.path.basename(output_path)
    mime = "audio/mpeg"

    file_like = open(output_path, "rb")
    upload_file = ConvertedUploadFile(
        filename=filename, file=file_like, content_type=mime
    )

    os.remove(input_path)
    return upload_file