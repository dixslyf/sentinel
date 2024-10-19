{
  pkgs,
  ...
}:
{
  packages = with pkgs; [ git ];

  languages.javascript = {
    enable = true;
    npm = {
      enable = true;
      package = pkgs.nodejs;
      install.enable = true;
    };
  };

  pre-commit.hooks = {
    eslint.enable = true;
  };
}
