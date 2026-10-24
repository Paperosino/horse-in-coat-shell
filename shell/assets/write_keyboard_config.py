"""Atomically persist the generated keyboard block in the user's configuration."""
import sys
from feature_common import CONFIG
from configuration_manager import write_text
def main():
 try:
  payload=sys.stdin.buffer.read(1048577)
  if not payload.strip() or len(payload)>1048576 or b'\0' in payload:
   raise ValueError('Invalid keyboard configuration payload')
  write_text(CONFIG/'keyboard.lua',payload.decode('utf-8'))
  return 0
 except (OSError,ValueError) as error:
  print(str(error),file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
