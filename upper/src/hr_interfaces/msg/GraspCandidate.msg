# One planar grasp proposal, already expressed in the arm's own base frame.
string object_class
float32 confidence            # detector confidence, 0..1
geometry_msgs/Point position  # grasp centre in arm_base_link
float32 grasp_angle           # rotation of the gripper about the approach axis, rad
float32 gripper_width         # required opening, m
float32 quality               # grasp quality, 0..1
float32 depth_valid_ratio     # fraction of valid depth pixels inside the bbox
