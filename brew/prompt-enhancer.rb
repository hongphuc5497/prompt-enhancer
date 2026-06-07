class PromptEnhancer < Formula
  include Language::Python::Virtualenv

  desc "Reverse-engineered from Auggie's Ctrl+P — rough ideas → production system prompts"
  homepage "https://github.com/hongphuc5497/prompt-enhancer"
  # Published to PyPI as `prompt-enhancer-cli` (the bare name was already taken).
  url "https://files.pythonhosted.org/packages/ea/33/1539a28522d359fb037cac70a5eb24123496253e2646888e2987ddab9d69/prompt_enhancer_cli-1.5.0.tar.gz"
  sha256 "63ad5539dd414f775f3dfe639055284350282896edaa4b84e3c75a8948dddb9c"
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
