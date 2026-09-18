std_msgs/Header header
# Empty whenever the frame could not be trusted; read reject_reason to find out
# why. An empty list is never the same as "nothing is graspable there".
GraspCandidate[] candidates
bool calibration_valid
bool depth_valid
string reject_reason          # empty when the frame was accepted
