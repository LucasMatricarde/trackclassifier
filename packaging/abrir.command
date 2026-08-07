#!/bin/bash
# App nao e notarizado pela Apple (exige conta paga) -- Gatekeeper marca
# tudo que vem de download com quarantine e recusa abrir direto. So precisa
# rodar isto uma vez; da segunda abertura em diante o Finder abre normal.
set -euo pipefail
cd "$(dirname "$0")"
echo "Liberando TrackClassifier pro Gatekeeper..."
xattr -cr TrackClassifier.app
open TrackClassifier.app
