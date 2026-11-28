! Replay the recorded fourth MS equation with the installed native FSILS.
! The observer writes the scaled recurrence at the two copies of node 7591.
      PROGRAM replay_ms
      INCLUDE "FSILS_STD.h"
      TYPE(FSILS_lhsType) lhs
      TYPE(FSILS_commuType) commu
      TYPE(FSILS_subLsType) ls
      INTEGER rank, code, n, gn, nz, owned, dof, unit, i, saved_it
      INTEGER trace_unit, probe_local
      COMMON /ms_trace/ trace_unit, probe_local
      INTEGER, ALLOCATABLE :: ids(:), perm(:), ptr(:), col(:)
      REAL(KIND=LSRP), ALLOCATABLE :: mask(:,:), b(:,:), a(:,:),
     &  r(:,:), wr(:,:), wc(:,:), saved_p(:,:), saved_x(:,:)
      REAL(KIND=LSRP) saved_i, saved_f, diffs(3), maxima(3)
      CHARACTER(512) folder
      CHARACTER(7) stem
      CALL MPI_INIT(code)
      CALL FSILS_COMMU_CREATE(commu,MPI_COMM_WORLD)
      rank=commu%task
      IF (commu%nTasks.NE.32) CALL MPI_ABORT(commu%comm,1,code)
      CALL GET_COMMAND_ARGUMENT(1,folder)
      WRITE(stem,'("ms-4",I3.3)') rank
      OPEN(NEWUNIT=unit,FILE=TRIM(folder)//'/ms-4-'//stem(5:7)//
     & '.raw',ACCESS='stream',FORM='unformatted',STATUS='old')
      READ(unit) n,gn,nz,owned,dof
      IF (dof.NE.3) CALL MPI_ABORT(commu%comm,2,code)
      ALLOCATE(ids(n),perm(n),ptr(n+1),col(nz))
      ALLOCATE(mask(3,n),b(3,n),a(9,nz),r(3,n),wr(3,n),wc(3,n))
      ALLOCATE(saved_p(9,nz),saved_x(3,n))
      READ(unit) ids,perm,ptr,col,mask,b,a
      CLOSE(unit)
      OPEN(NEWUNIT=unit,FILE=TRIM(folder)//'/ms-4-'//stem(5:7)//
     & '.returned',ACCESS='stream',FORM='unformatted',STATUS='old')
      READ(unit) saved_it,saved_i,saved_f,saved_x,saved_p
      CLOSE(unit)
      CALL FSILS_LHS_CREATE(lhs,commu,gn,n,nz,ids,ptr,col,1)
      IF (ANY(perm.NE.lhs%map).OR.owned.NE.lhs%mynNo)
     & CALL MPI_ABORT(commu%comm,3,code)
! Reuse the recorded local product of included Dirichlet masks.
! PRECONDRCS performs the same native sum, threshold, and row/col scaling.
      lhs%face(1)%incFlag=.TRUE.
      lhs%face(1)%bGrp=BC_TYPE_Dir
      lhs%face(1)%nNo=n
      lhs%face(1)%dof=3
      ALLOCATE(lhs%face(1)%glob(n),lhs%face(1)%val(3,n))
      lhs%face(1)%glob=perm
      lhs%face(1)%val=mask
      r(:,perm)=b
      CALL PRECONDRCS(lhs,lhs%rowPtr,lhs%colPtr,lhs%diagPtr,3,a,r,wr,wc)
      IF (ANY(a.NE.saved_p)) CALL MPI_ABORT(commu%comm,4,code)
      probe_local=0
      IF (rank.EQ.21.OR.rank.EQ.24) THEN
         DO i=1,n
            IF (ids(i).EQ.7591) probe_local=perm(i)
         END DO
         IF (probe_local.EQ.0) CALL MPI_ABORT(commu%comm,5,code)
         OPEN(NEWUNIT=trace_unit,FILE='trace-'//stem(5:7)//'.dat',
     &     STATUS='new')
         WRITE(trace_unit,*) wc(3,probe_local),wr(3,probe_local)
      END IF
      ls%relTol=1.e-10_LSRP
      ls%absTol=1.e-23_LSRP
      ls%mItr=2000
      CALL CGRADV(lhs,ls,3,a,r)
      IF (probe_local.GT.0) CLOSE(trace_unit)
      r=wc*r
      diffs(1)=ABS(ls%iNorm-saved_i)
      diffs(2)=ABS(ls%fNorm-saved_f)
      diffs(3)=MAXVAL(ABS(r(:,perm)-saved_x))
      CALL MPI_ALLREDUCE(diffs,maxima,3,mpreal,MPI_MAX,commu%comm,code)
      IF (rank.EQ.0) WRITE(*,*) 'replay',saved_it,ls%itr,maxima
      IF (ls%itr.NE.saved_it.OR.ANY(maxima.NE.0._LSRP))
     & CALL MPI_ABORT(commu%comm,6,code)
      CALL MPI_FINALIZE(code)
      END PROGRAM replay_ms
