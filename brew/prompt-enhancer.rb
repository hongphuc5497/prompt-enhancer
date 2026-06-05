class PromptEnhancer < Formula
  desc "Reverse-engineered from Auggie's Ctrl+P — rough ideas → production system prompts"
  homepage "https://github.com/hongphuc5497/prompt-enhancer"
  url "https://github.com/hongphuc5497/prompt-enhancer/archive/refs/tags/v1.5.0.tar.gz"
  sha256 "REPLACE_WITH_ACTUAL_SHA256"
  license "MIT"

  depends_on "python@3.13"

  def install
    # Install Python package
    system "python3", "-m", "pip", "install", "--prefix=#{prefix}", "."

    # Create the CLI entry point manually (no pip scripts on some setups)
    (bin/"prompt-enhancer").write <<~EOS
      #!/bin/sh
      exec "#{Formula["python@3.13"].opt_bin}/python3" -m prompt_enhancer.cli "$@"
    EOS
    chmod 0755, bin/"prompt-enhancer"
  end

  test do
    system "#{bin}/prompt-enhancer", "version"
  end
end
