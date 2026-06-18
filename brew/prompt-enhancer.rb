class PromptEnhancer < Formula
  include Language::Python::Virtualenv

  desc "Reverse-engineered from Auggie's Ctrl+P — rough ideas → production system prompts"
  homepage "https://github.com/hongphuc5497/prompt-enhancer"
  # Published to PyPI as `prompt-enhancer-cli` (the bare name was already taken).
  url "https://files.pythonhosted.org/packages/72/87/403d3b7b60c43e4fa421194404319a07f4f63458e7553f1a3ff16af475d7/prompt_enhancer_cli-1.6.1.tar.gz"
  sha256 "62d35b528ded087ade0c530e99782267b7c065d24b92eb70635cbbf85365b842"
  license "MIT"

  depends_on "python@3.13"

  # Zero runtime dependencies (Python stdlib only), so no `resource` blocks
  # are required — virtualenv_install_with_resources installs the sdist alone
  # and links both `pe` and `prompt-enhancer` console scripts into bin.
  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "prompt-enhancer #{version}", shell_output("#{bin}/pe version")
    assert_match "prompt-enhancer #{version}", shell_output("#{bin}/prompt-enhancer version")
  end
end
