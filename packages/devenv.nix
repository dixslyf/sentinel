{
  pkgs,
  inputs,
  ...
}:

let
  pkgs-unstable = inputs.nixpkgs-unstable.legacyPackages.${pkgs.stdenv.system};
in
{
  packages = with pkgs; [ git ];

  languages.python = {
    enable = true;
    package = pkgs.python312;
    poetry.enable = true;
  };

  pre-commit.hooks = {
    black = {
      enable = true;
      package = pkgs-unstable.black;
    };
  };
}
