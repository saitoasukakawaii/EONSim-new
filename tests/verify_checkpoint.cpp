/** 单 rank 写失败、发布失败与遗留目录均不得覆盖最后一次完整 accepted 状态。 */
#include "eonsim/checkpoint.hpp"
#include <hdf5.h>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <stdexcept>
#include <iomanip>

using namespace eonsim;
namespace {
void require(bool condition,const char* message) { if(!condition) throw std::runtime_error(message); }
std::string bytes(const std::filesystem::path& path) {
    std::ifstream in(path,std::ios::binary);
    require(bool(in),"Cannot read verification file");
    return std::string(std::istreambuf_iterator<char>(in),{});
}
std::filesystem::path current(const std::filesystem::path& dir) {
    std::ifstream in(dir/"current"); std::string format,name; in>>format>>name;
    require(format=="EONSim_checkpoint_v4","Bad current pointer format"); return dir/name;
}
void verify(const std::filesystem::path& dir) {
    MeshPartition mesh; MPI_Comm_rank(MPI_COMM_WORLD,&mesh.rank); MPI_Comm_size(MPI_COMM_WORLD,&mesh.ranks);
    mesh.owned_nodes=1; mesh.owned_begin=mesh.rank; mesh.global_nodes=mesh.ranks;
    if(mesh.rank==0) { std::filesystem::remove_all(dir); std::filesystem::create_directories(dir); }
    MPI_Barrier(MPI_COMM_WORLD);
    const std::uint64_t signature=1357+mesh.rank;
    const std::map<std::string,std::size_t> sizes{{"empty",0},{"u",2}};
    const Checkpoint first{1,{{"empty",{}},{"u",{double(mesh.rank),2}}},.125,.0625,0x1p-60};
    auto put=[&](const Checkpoint& state){write_checkpoint(MPI_COMM_WORLD,dir,mesh,signature,state);};
    auto get=[&](const std::filesystem::path& path){return read_checkpoint(path,mesh,signature,sizes);};
    put(first);
    const auto old=current(dir),rankfile=old/("state_rank"+std::to_string(mesh.rank)+".h5");
    const auto pointer=bytes(dir/"current"),contents=bytes(rankfile);
    auto previous_survives=[&] {
        require(bytes(dir/"current")==pointer,"Failed generation changed current pointer");
        require(bytes(rankfile)==contents,"Failed generation overwrote prior rank data");
        const auto restored=get(dir);
        require(restored.step==first.step&&restored.time==first.time&&restored.next_dt==first.next_dt&&
            restored.time_correction==first.time_correction&&restored.fields==first.fields,
            "Previous accepted state was not recovered");
    };
    Checkpoint next{2,{{"empty",{}},{"u",{double(mesh.rank)+3,4}}},.1875,.03125,-0x1p-60};
    auto nonfinite=next;
    if(mesh.rank==mesh.ranks-1) nonfinite.time_correction=std::numeric_limits<double>::quiet_NaN();
    bool failed=false;
    try {put(nonfinite);} catch(const std::runtime_error& e) {failed=std::string(e.what()).find("validation")!=std::string::npos;}
    require(failed,"Nonfinite time correction was not rejected collectively");previous_survives();
    if(mesh.ranks>1) {
        auto mismatch=next;if(mesh.rank==mesh.ranks-1) mismatch.time_correction=0;
        failed=false;
        try {put(mismatch);} catch(const std::runtime_error& e) {failed=std::string(e.what()).find("clock across ranks")!=std::string::npos;}
        require(failed,"Rank-dependent time correction was accepted");previous_survives();
    }
    // 最后一个 rank 在部分 HDF5 数据已写出后遇到真实 dataset 创建错误；所有 rank 应返回异常。
    auto bad=next;
    if(mesh.rank==mesh.ranks-1) bad.fields["missing_group/value"]={1};
    failed=false;
    try { put(bad); } catch(const std::runtime_error& e) { failed=std::string(e.what()).find("rank write")!=std::string::npos; }
    require(failed,"Rank write failure did not reach every rank"); previous_survives();
    // 所有 HDF5 文件可成功关闭，但指针临时文件被目录阻挡，模拟最后发布阶段的 I/O 失败。
    if(mesh.rank==0) std::filesystem::create_directory(dir/"current.tmp");
    MPI_Barrier(MPI_COMM_WORLD); failed=false;
    try { put(next); } catch(const std::runtime_error& e) { failed=std::string(e.what()).find("publication")!=std::string::npos; }
    require(failed,"Publication failure did not reach every rank"); previous_survives();
    if(mesh.rank==0) std::filesystem::remove(dir/"current.tmp");
    MPI_Barrier(MPI_COMM_WORLD);
    put(next); const auto second=current(dir);
    require(second!=old&&get(dir).fields==next.fields,"New generation did not publish");
    require(get(old).fields==first.fields,"Explicit previous generation cannot be recovered");
    put(next); require(current(dir)!=second,"Repeated accepted step overwrote a generation");
    require(bytes(rankfile)==contents,"Successful publication overwrote prior rank data");
    // A genuine legacy layout has a two-value clock and version3 metadata.
    // It remains readable, explicitly losing only the unavailable correction.
    const auto legacy=dir/"legacy";
    if(mesh.rank==0) std::filesystem::create_directory(legacy);
    MPI_Barrier(MPI_COMM_WORLD);
    const auto legacyfile=legacy/rankfile.filename();std::filesystem::copy_file(rankfile,legacyfile);
    hid_t file=H5Fopen(legacyfile.c_str(),H5F_ACC_RDWR,H5P_DEFAULT);require(file>=0,"Cannot create legacy fixture");
    hid_t meta=H5Dopen2(file,"metadata",H5P_DEFAULT);std::uint64_t metadata[9]{};
    require(meta>=0&&H5Dread(meta,H5T_NATIVE_UINT64,H5S_ALL,H5S_ALL,H5P_DEFAULT,metadata)>=0,"Cannot read fixture metadata");
    metadata[0]=3;require(H5Dwrite(meta,H5T_NATIVE_UINT64,H5S_ALL,H5S_ALL,H5P_DEFAULT,metadata)>=0,"Cannot write legacy metadata");
    require(H5Dclose(meta)>=0&&H5Ldelete(file,"clock",H5P_DEFAULT)>=0,"Cannot replace fixture clock");
    const hsize_t count=2;hid_t space=H5Screate_simple(1,&count,nullptr);
    hid_t dataset=H5Dcreate2(file,"clock",H5T_NATIVE_DOUBLE,space,H5P_DEFAULT,H5P_DEFAULT,H5P_DEFAULT);
    const double legacy_clock[]={first.time,first.next_dt};
    require(dataset>=0&&H5Dwrite(dataset,H5T_NATIVE_DOUBLE,H5S_ALL,H5S_ALL,H5P_DEFAULT,legacy_clock)>=0,"Cannot write legacy clock");
    require(H5Dclose(dataset)>=0&&H5Sclose(space)>=0&&H5Fclose(file)>=0,"Cannot close legacy fixture");
    if(mesh.rank==0) {
        std::ofstream manifest(legacy/"manifest");
        manifest<<std::setprecision(17)<<"EONSim_checkpoint_v3 "<<mesh.ranks<<' '<<first.step<<' '<<first.time<<' '<<first.next_dt<<'\n';
    }
    MPI_Barrier(MPI_COMM_WORLD);
    const auto legacy_state=get(legacy);
    require(legacy_state.time==first.time&&legacy_state.next_dt==first.next_dt&&legacy_state.time_correction==0&&
            legacy_state.fields==first.fields,"Legacy checkpoint fallback changed known accepted state");
    // All readers must finish before rank 0 deliberately corrupts the pointer.
    MPI_Barrier(MPI_COMM_WORLD);
    if(mesh.rank==0) { std::ofstream out(dir/"current"); out<<"EONSim_checkpoint_v4 ../escape\n"; }
    MPI_Barrier(MPI_COMM_WORLD); failed=false;
    try { get(dir); } catch(const std::runtime_error& e) { failed=std::string(e.what()).find("current pointer")!=std::string::npos; }
    require(failed,"Invalid generation pointer was accepted");
    if(mesh.rank==0) std::cout<<"checkpoint publication failure/recovery passed on "<<mesh.ranks<<" ranks\n";
}
}
int main(int argc,char** argv) {
    MPI_Init(&argc,&argv);
    try { require(argc==2,"Expected a dedicated test directory"); verify(argv[1]); }
    catch(const std::exception& e) { std::cerr<<e.what()<<'\n'; MPI_Abort(MPI_COMM_WORLD,1); }
    return MPI_Finalize();
}
