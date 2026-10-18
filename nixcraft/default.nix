{...}: let
  inherit (builtins) fromJSON readFile;

  sources = {
    libraries = fromJSON (readFile ./libraries.json);
    mojang = fromJSON (readFile ./mojang.json);
    fabric = fromJSON (readFile ./fabric.json);
    quilt = fromJSON (readFile ./quilt.json);
    forge = fromJSON (readFile ./forge.json);
    neoforge = fromJSON (readFile ./neoforge.json);
    lwjgl = fromJSON (readFile ./lwjgl.json);

    paper = fromJSON (readFile ./paper.json);
    folia = fromJSON (readFile ./folia.json);
    purpur = fromJSON (readFile ./purpur.json);
    velocity = fromJSON (readFile ./velocity.json);
    waterfall = fromJSON (readFile ./waterfall.json);

    asset-sha1-sha256-map = fromJSON (readFile ./asset-sha1-sha256-map.json);
    waywall = fromJSON (readFile ./waywall.json);
  };
in {
  # The reason this attr exists is to provide forward and backward compatibility
  # when downstream Nixcraft pins or overrides this sources repository.
  #
  # If a newer commit introduces breaking schema changes (e.g., protocol "2"),
  # older Nixcraft installations will still fetch their expected protocol version
  # via `version."1"`, allowing this bridge to adapt or emulate the older format
  # seamlessly without breaking evaluation.
  version = {
    "1" = sources;
  };

  currentVersion = 1;
  supportedBackwardVersions = [1];
}
