std_msgs/Header header
uint8 ZERO=0
uint8 NAVIGATING=1
uint8 FOLLOWING=2
uint8 DOCKING=3
uint8 phase
# Monotonic counter of the authorising task manager. hr_motion_mux ignores any
# phase message whose source_seq does not advance, so a late message from an
# already-left phase can never re-authorise a speed source.
uint32 source_seq
string task_id
string reason
bool zero_required
