/** 单 rank 写失败、发布失败与遗留目录均不得覆盖最后一次完整 accepted 状态。 */
#include "eonsim/checkpoint.hpp"
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <stdexcept>

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
    require(format=="EONSim_checkpoint_v3","Bad current pointer format"); return dir/name;
}
void verify(const std::filesystem::path& dir) {
    MeshPartition mesh; MPI_Comm_rank(MPI_COMM_WORLD,&mesh.rank); MPI_Comm_size(MPI_COMM_WORLD,&mesh.ranks);
    mesh.owned_nodes=1; mesh.owned_begin=mesh.rank; mesh.global_nodes=mesh.ranks;
    if(mesh.rank==0) { std::filesystem::remove_all(dir); std::filesystem::create_directories(dir); }
    MPI_Barrier(MPI_COMM_WORLD);
    const std::uint64_t signature=1357+mesh.rank;
    const std::map<std::string,std::size_t> sizes{{"empty",0},{"u",2}};
    const Checkpoint first{1,{{"empty",{}},{"u",{double(mesh.rank),2}}},.125,.0625};
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
            restored.fields==first.fields,"Previous accepted state was not recovered");
    };
    Checkpoint next{2,{{"empty",{}},{"u",{double(mesh.rank)+3,4}}},.1875,.03125};
    // 最后一个 rank 在部分 HDF5 数据已写出后遇到真实 dataset 创建错误；所有 rank 应返回异常。
    auto bad=next;
    if(mesh.rank==mesh.ranks-1) bad.fields["missing_group/value"]={1};
    bool failed=false;
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
    if(mesh.rank==0) { std::ofstream out(dir/"current"); out<<"EONSim_checkpoint_v3 ../escape\n"; }
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
