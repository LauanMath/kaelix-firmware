#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <cstdio>
namespace kaelix::receiver {
struct RemoteLog {
 uint32_t sequence=0;
 uint64_t uptime_ms=0;
 char level[6]{}, event[25]{}, message[384]{};
 bool truncated=false;
};
// Caller synchronizes access; the HTTP snapshot never removes pending logs.
template<size_t Capacity> class LogBuffer {
 RemoteLog entries[Capacity]{};
 size_t head=0,used=0;
 uint32_t sequence=0;
public:
 bool push(uint64_t ms,const char* level,const char* event,const char* message,bool truncated=false){
  if(sequence==UINT32_MAX)return false;
  const uint32_t next=++sequence;
  if(used==Capacity)return false; // drop newest, expose gaps in log_seq
  auto& entry=entries[(head+used++)%Capacity];
  entry.sequence=next;entry.uptime_ms=ms;
  snprintf(entry.level,sizeof(entry.level),"%s",level);
  snprintf(entry.event,sizeof(entry.event),"%s",event);
  size_t len=strlen(message),n=len<sizeof(entry.message)?len:sizeof(entry.message)-1;
  if(n<len)while(n && (static_cast<unsigned char>(message[n])&0xC0)==0x80)--n;
  memcpy(entry.message,message,n);entry.message[n]=0;
  entry.truncated=truncated || n<len;
  return true;
 }
 size_t snapshot(RemoteLog* out,size_t limit)const{
  size_t count=used<limit?used:limit;
  for(size_t i=0;i<count;++i)out[i]=entries[(head+i)%Capacity];
  return count;
 }
 void pop(size_t count){if(count<=used){head=(head+count)%Capacity;used-=count;}}
 size_t size()const{return used;}
};
}
