#!/bin/zsh
# usage: fetch.sh <manifest-file-substring>  -> downloads into wave2/raw/<dataset>/<file>, verifies byte count
set -e
cd "$(dirname $0)/.."
line=$(grep -F "$1" reports/dataset_audit/file_manifest.csv | grep -o '^[^,]*,[^,]*,[^,]*,[^,]*,[^,]*' | head -1)
rel=$(echo $line | cut -d, -f2); bytes=$(echo $line | cut -d, -f5)
url=$(grep -F "$rel" reports/dataset_audit/file_manifest.csv | grep -o 'https://[^,]*dropbox[^,]*' | head -1); url=${url/dl.dropboxusercontent.com/www.dropbox.com}; url="${url%%&dl*}&dl=0"
out=wave2/raw/$rel; mkdir -p $(dirname $out)
[[ -f $out && $(stat -f%z $out) == $bytes ]] && { echo "have $rel"; exit 0; }
curl -sfL --retry 3 -o $out.part "${url/dl=0/dl=1}"
got=$(stat -f%z $out.part); [[ $got == $bytes ]] || { echo "SIZE MISMATCH $rel $got != $bytes"; rm $out.part; exit 1; }
mv $out.part $out; echo "ok $rel $bytes"
