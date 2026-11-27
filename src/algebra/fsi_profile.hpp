#pragma once
#include <petsclog.h>

namespace eonsim {
template<class Operation>
inline PetscErrorCode profile_fsi_operation(PetscLogEvent event,Operation&& operation) {
    if(event<0) return operation();
    PetscCall(PetscLogEventBegin(event,nullptr,nullptr,nullptr,nullptr));
    const PetscErrorCode error=operation();
    PetscCall(PetscLogEventEnd(event,nullptr,nullptr,nullptr,nullptr));
    return error;
}
}
