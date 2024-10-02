{ pkgs, lib, config, inputs, ... }:

{
  packages = with pkgs; [ git ];

  languages.python = {
    enable = true;
    package = pkgs.python312;
    poetry = {
      enable = true;
      install = {
        enable = true;
        installRootPackage = true;
      };
      activate.enable = true;
    };
  };

  pre-commit.hooks = {
    black.enable = true;
  };
}
