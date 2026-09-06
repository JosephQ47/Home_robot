#include "status_snapshot.h"
#include <string.h>
void status_snapshot_zero(Robot_Status_t *s){if(s!=0)memset(s,0,sizeof(*s));}
