#!/bin/bash

# Configuration
SECRETS_REPO="https://github.com/Fuerza-Leona/callsight-secrets.git"
ENV_FILE_NAME=".env.back"  # The file name in the secrets repo
LOCAL_ENV_PATH=".env"      # Where to put it in your project

# Save the original directory
ORIGINAL_DIR=$(pwd)

# Create a temporary directory
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

echo "Fetching latest environment variables..."

# Clone only the specific file from the secrets repo (shallow clone)
git clone --depth 1 "$SECRETS_REPO" .

# Check if clone was successful
if [ $? -ne 0 ]; then
  echo "Error: Failed to clone secrets repository."
  cd - > /dev/null
  rm -rf "$TEMP_DIR"
  exit 1
fi

# Check if the environment file exists
if [ ! -f "$ENV_FILE_NAME" ]; then
  echo "Error: Environment file '$ENV_FILE_NAME' not found in secrets repository."
  cd - > /dev/null
  rm -rf "$TEMP_DIR"
  exit 1
fi

# Copy the environment file to the correct location
cp "$ENV_FILE_NAME" "$ORIGINAL_DIR/$LOCAL_ENV_PATH"

# Clean up
cd - > /dev/null
rm -rf "$TEMP_DIR"

echo "Environment file updated successfully to $LOCAL_ENV_PATH!"
