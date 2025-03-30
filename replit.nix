{pkgs}: {
  deps = [
    pkgs.chromium
    pkgs.jq
    pkgs.geckodriver
    pkgs.postgresql
    pkgs.openssl
  ];
}
