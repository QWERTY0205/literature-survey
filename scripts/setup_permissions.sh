#!/bin/bash
# Grant Claude Code the necessary permissions for the literature survey workspace.
# Usage: ./setup_permissions.sh <workspace_dir>
#
# Example: ./setup_permissions.sh /data/paper/full_duplex_speech

set -e
WORKSPACE="${1:-/data/paper}"

# Ensure poppler-utils is installed for pdftotext
if ! command -v pdftotext >/dev/null 2>&1; then
    echo "Installing poppler-utils..."
    apt-get install -y poppler-utils
fi

# Clone papers-cool-downloader if not present
if [ ! -d /tmp/papers-cool-downloader ]; then
    echo "Cloning papers-cool-downloader..."
    git clone https://github.com/QWERTY0205/papers-cool-downloader /tmp/papers-cool-downloader
    pip install requests
fi

# Create project-level settings.local.json with auto-accept
mkdir -p "$WORKSPACE/.claude"
cat > "$WORKSPACE/.claude/settings.local.json" <<'EOF'
{
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "Read",
      "Write",
      "Edit",
      "Bash(cd:*)",
      "Bash(ls:*)",
      "Bash(mkdir:*)",
      "Bash(rm:*)",
      "Bash(cp:*)",
      "Bash(mv:*)",
      "Bash(cat:*)",
      "Bash(grep:*)",
      "Bash(find:*)",
      "Bash(head:*)",
      "Bash(tail:*)",
      "Bash(wc:*)",
      "Bash(python3:*)",
      "Bash(python:*)",
      "Bash(pip:*)",
      "Bash(pip3:*)",
      "Bash(pdftotext:*)",
      "Bash(pdftoppm:*)",
      "Bash(wget:*)",
      "Bash(curl:*)",
      "Bash(git:*)",
      "Bash(jq:*)",
      "WebFetch(domain:arxiv.org)",
      "WebFetch(domain:papers.cool)",
      "WebFetch(domain:github.com)",
      "WebFetch(domain:openreview.net)",
      "WebFetch(domain:aclanthology.org)",
      "WebFetch(domain:openaccess.thecvf.com)",
      "WebFetch(domain:ojs.aaai.org)",
      "WebFetch(domain:huggingface.co)",
      "WebSearch"
    ]
  }
}
EOF

# Also update global settings to allow sub-agents to access the workspace
GLOBAL_SETTINGS="$HOME/.claude/settings.json"
if [ -f "$GLOBAL_SETTINGS" ]; then
    echo "Note: append '$WORKSPACE' to additionalDirectories in $GLOBAL_SETTINGS"
    echo "      for sub-agents to access this workspace."
fi

echo "✓ Workspace $WORKSPACE ready"
echo "  Launch Claude Code from: cd $WORKSPACE && claude"
