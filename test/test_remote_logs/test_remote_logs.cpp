#include <unity.h>
#include "../../src/receiver/log_buffer.h"
using namespace kaelix::receiver;
void setUp(){} void tearDown(){}
void test_snapshot_retains_pending_logs_and_exposes_overflow_gap(){
 LogBuffer<2> q;RemoteLog snapshot[2];
 TEST_ASSERT_TRUE(q.push(100,"INFO","RX","one"));TEST_ASSERT_TRUE(q.push(200,"ERROR","SPI","two"));
 TEST_ASSERT_FALSE(q.push(300,"INFO","HEALTH","lost"));
 TEST_ASSERT_EQUAL(2,q.snapshot(snapshot,2));TEST_ASSERT_EQUAL(1,snapshot[0].sequence);
 q.pop(1);TEST_ASSERT_TRUE(q.push(400,"INFO","RX","four"));
 TEST_ASSERT_EQUAL(2,q.snapshot(snapshot,2));TEST_ASSERT_EQUAL(2,snapshot[0].sequence);TEST_ASSERT_EQUAL(4,snapshot[1].sequence);
 TEST_ASSERT_EQUAL_STRING("two",snapshot[0].message);TEST_ASSERT_EQUAL(200,snapshot[0].uptime_ms);
}
void test_diagnostic_messages_are_bounded_and_utf8_boundary_preserved(){
 LogBuffer<2> q;char message[500];memset(message,'a',382);strcpy(message+382,"éxxxx");
 TEST_ASSERT_TRUE(q.push(1,"WARN","QUEUE",message));RemoteLog out[2];q.snapshot(out,2);
 TEST_ASSERT_TRUE(out[0].truncated);TEST_ASSERT_EQUAL(382,strlen(out[0].message));
 TEST_ASSERT_TRUE(q.push(2,"INFO","RX","already shortened",true));q.snapshot(out,2);TEST_ASSERT_TRUE(out[1].truncated);
}
int main(){UNITY_BEGIN();RUN_TEST(test_snapshot_retains_pending_logs_and_exposes_overflow_gap);RUN_TEST(test_diagnostic_messages_are_bounded_and_utf8_boundary_preserved);return UNITY_END();}
