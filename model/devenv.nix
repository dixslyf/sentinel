{
  pkgs,
  ...
}:

{
  packages = with pkgs; [ git ];

  languages.python = {
    enable = true;
    package = pkgs.python312;
    libraries = with pkgs; [
      stdenv.cc.cc.lib
    ];
    poetry = {
      enable = true;
    };
  };

  env.FIFTYONE_DATABASE_URI = "mongodb://localhost:27017";
  services.mongodb.enable = true;
}
