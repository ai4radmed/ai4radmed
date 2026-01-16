#!/bin/bash
# C-MOVE: Study를 Mock에서 Raw로 이동
# Usage: docker exec ai4radmed-dicom-tools /examples/03_move_study.sh <STUDY_UID>

set -e

STUDY_UID=${1?"Usage: $0 <STUDY_INSTANCE_UID>"}

echo "=== Moving Study from Mock to Raw PACS ==="
echo "Study UID: $STUDY_UID"

# C-MOVE 명령
# -aem: Move Destination AET (Raw PACS)
# +P: Destination Port (Raw PACS의 DICOM 포트)
movescu -v \
  -aet CLIENT \
  -aec MOCK_PACS \
  ai4radmed-orthanc-mock 4242 \
  -aem RAW_PACS \
  +P 4242 \
  -k QueryRetrieveLevel=STUDY \
  -k StudyInstanceUID="$STUDY_UID"

echo "✓ Move request sent successfully"
echo "Note: Check Raw PACS to verify data transfer"
