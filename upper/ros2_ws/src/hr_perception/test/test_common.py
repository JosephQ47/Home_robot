from std_msgs.msg import Header

from hr_perception.common import Latest, detections_message, fresh


def test_latest_replaces_backlog():
    box = Latest()
    box.put('old')
    box.put('new')
    assert box.get() == (2, 'new')


def test_staleness_and_clock_boundary():
    assert fresh(10., 2., now=12.)
    assert not fresh(10., 2., now=12.01)
    assert not fresh(10., 2., now=9.)


def test_boxes_clipped_with_original_header_and_labels():
    header = Header(frame_id='camera_optical_frame')
    header.stamp.sec = 123
    out = detections_message(header, [[-10, 20, 110, 80, .8, 0]], {0: 'person'}, 100, 100)
    box = out.detections[0]
    assert out.header == box.header == header
    assert box.bbox.center.position.x == 50
    assert box.bbox.center.position.y == 50
    assert box.bbox.size_x == 100
    assert box.bbox.size_y == 60
    assert box.results[0].hypothesis.class_id == 'person'


def test_empty_and_invalid_detections():
    rows = [[2, 0, 1, 10, .8, 0], [0, 0, 2, 2, float('nan'), 0]]
    assert not detections_message(Header(), rows, {0: 'person'}, 100, 100).detections
    assert not detections_message(Header(), [], {}, 100, 100).detections
