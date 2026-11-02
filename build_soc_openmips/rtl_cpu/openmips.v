/*
 * @Author: Groot
 * @Date: 2022-04-12 16:04:07
 * @LastEditTime: 2022-05-18 11:24:26
 * @LastEditors: Groot
 * @Description:
 * @FilePath: /openMIPS/vsrc/openmips.v
 * 版权声明
 */
`include "define.v"
// `include "ex_mem.v"
// `include "ex.v"
// `include "hilo_reg.v"
// `include "id_ex.v"
// `include "id.v"
// `include "if_id.v"
// `include "inst_rom.v"
// `include "mem_wb.v"
// `include "mem.v"
// `include "pc_reg.v"
// `include "regfile.v"
// `include "ctrl.v"

module openmips (input wire clk,
                 input wire rst,
                 input wire dbg_stall_i,
                 input wire[`RegBus] rom_data_i,  //存疑
                 output wire[`RegBus] rom_addr_o, //存疑
                 output wire rom_ce_o,
                 input wire[`RegBus] ram_data_i,
                 output wire[`RegBus] ram_addr_o,
                 output wire[`RegBus] ram_data_o,
                 output wire ram_we_o,
                 output wire ram_ce_o,
                 output wire[3:0] ram_sel_o
                 );
    //连接 IF/ID模块与译码阶段ID模块的变量
    wire[`InstAddrBus] pc;
    wire[`InstAddrBus] id_pc_i;
    wire[`InstBus] id_inst_i;
    
    //连接译码阶段ID模块输出与ID/EX模块输入的变量
    wire[`AluOpBus] id_aluop_o;
    wire[`AluSelBus] id_alusel_o;
    wire[`RegBus] id_reg1_o;
    wire[`RegBus] id_reg2_o;
    wire id_wreg_o;
    wire[`RegAddBus] id_wd_o;
    wire id_is_in_delayslot_o;
    wire[`RegBus] id_link_addr_o;
    wire id_next_inst_in_delayslot_o;
    wire[`RegBus] id_inst_o;

    //连接ID/EX模块输出与执行阶段EX模块输入的变量
    wire[`AluOpBus] ex_aluop_i;
    wire[`AluSelBus] ex_alusel_i;
    wire[`RegBus] ex_reg1_i;
    wire[`RegBus] ex_reg2_i;
    wire ex_wreg_i;
    wire[`RegAddBus] ex_wd_i;
    wire[`RegBus] ex_inst_i;

    
    //连接执行阶段EX模块的输出与EX/MEM模块的输入的变量
    wire ex_wreg_o;
    wire[`RegAddBus] ex_wd_o;
    wire[`RegBus] ex_wdata_o;
    wire ex_whilo_o;
    wire[`RegBus] ex_hi_o;
    wire[`RegBus] ex_lo_o;
    wire[`AluOpBus] ex_aluop_o;
    wire[`RegBus] ex_mem_addr_o;
    wire[`RegBus] ex_reg2_o;
    wire ex_is_in_delayslot_i;

    // ---- multi-cycle divider nets ----
    wire[`DoubleRegBus] div_result;
    wire                div_ready;
    wire[`RegBus]       div_opdata1;
    wire[`RegBus]       div_opdata2;
    wire                div_start;
    wire                signed_div;
    wire[`RegBus] ex_link_address_i;
    
    //连接EX/MEM模块的输出与访存阶段MEM模块的输入的变量
    wire mem_wreg_i;
    wire[`RegAddBus] mem_wd_i;
    wire[`RegBus] mem_wdata_i;
    wire mem_whilo_i;
    wire[`RegBus] mem_hi_i;
    wire[`RegBus] mem_lo_i;
    wire[`AluOpBus] mem_aluop_i;
    wire[`RegBus] mem_mem_addr_i;
    wire[`RegBus] mem_reg2_i;
    
    //连接访存阶段MEM模块的输出与MEM/WB模块的输入的变量
    wire mem_wreg_o;
    wire[`RegAddBus] mem_wd_o;
    wire[`RegBus] mem_wdata_o;
    wire mem_whilo_o;
    wire[`RegBus] mem_hi_o;
    wire[`RegBus] mem_lo_o;
    
    //连接MEM/WB模块的输出与写回阶段的输入的变量
    wire wb_wreg_i;
    wire[`RegAddBus] wb_wd_i;
    wire[`RegBus] wb_wdata_i;
    wire wb_whilo_i;
    wire[`RegBus] wb_hi_i;
    wire[`RegBus] wb_lo_i;
    
    //连接译码阶段ID模块与通用寄存器Regfile模块的变量
    wire reg1_read;
    wire reg2_read;
    wire[`RegBus] reg1_data;
    wire[`RegBus] reg2_data;
    wire[`RegAddBus] reg1_addr;
    wire[`RegAddBus] reg2_addr;
    
    //连接执行阶段和HILO模块的输出，读取HI、LO寄存器
    wire[`RegBus] hi;
    wire[`RegBus] lo;
    
    // 用于流水线暂停的连线
    wire[5:0] stall;
    wire stallreq_from_id;
    wire stallreq_from_ex;

    // 用于累乘加、累乘减指令的ex模块和ex/mem模块的连线
    wire[1:0] cnt_i;
    wire[`DoubleRegBus] hilo_temp_i;
    wire[1:0] cnt_o;
    wire[`DoubleRegBus] hilo_temp_o;

    wire is_in_delayslot_i;
    wire is_in_delayslot_o;
    wire[`RegBus] branch_target_address;
    wire id_branch_flag_o;
    
    //pc_reg的例化
    pc_reg pc_reg0(.clk(clk),
    .rst(rst),
    .pc(pc),
    .ce(rom_ce_o),
    .stall(stall),
    .branch_target_address_i(branch_target_address),
    .branch_flag_i(id_branch_flag_o));
    
    assign rom_addr_o = pc;
    
    //IF/ID模块的例化
    if_id if_id0(.clk(clk),
    .rst(rst),
    .if_pc(pc),
    .if_inst(rom_data_i),
    .id_pc(id_pc_i),
    .id_inst(id_inst_i),
    .stall(stall));
    
    //译码阶段ID模块的例化
    id id0(.rst(rst),
    .pc_i(id_pc_i),
    .inst_i(id_inst_i),
    //来自Regfile的输入
    .reg1_data_i(reg1_data),
    .reg2_data_i(reg2_data),
    
    //处于执行阶段的指令要写入的目的寄存器信息
    .ex_aluop_i(ex_aluop_o),
    .ex_wreg_i(ex_wreg_o),
    .ex_wdata_i(ex_wdata_o),
    .ex_wd_i(ex_wd_o),
    
    //处于访存阶段的指令要写入的目的寄存器信息
    .mem_wreg_i(mem_wreg_o),
    .mem_wdata_i(mem_wdata_o),
    .mem_wd_i(mem_wd_o),
    
    //送到Regfile的信息
    .reg1_read_o(reg1_read),
    .reg2_read_o(reg2_read),
    .reg1_addr_o(reg1_addr),
    .reg2_addr_o(reg2_addr),
    //送到ID/EX模块的信息
    .aluop_o(id_aluop_o),
    .alusel_o(id_alusel_o),
    .reg1_o(id_reg1_o),
    .reg2_o(id_reg2_o),
    .wd_o(id_wd_o),
    .wreg_o(id_wreg_o),

    // 流水线暂停指令输出
    .stallreq(stallreq_from_id),

    // 用于转移指令的连线
    .is_in_delayslot_o(id_is_in_delayslot_o),
    .link_addr_o(id_link_addr_o),
    .next_inst_in_delayslot_o(id_next_inst_in_delayslot_o),
    .branch_target_address_o(branch_target_address),
    .branch_flag_o(id_branch_flag_o),
    .is_in_delayslot_i(is_in_delayslot_o),

    .inst_o(id_inst_o)
    );
    
    //通用寄存器Regfile的例化
    regfile regfile1(.clk(clk),
    .rst(rst),
    .we(wb_wreg_i & (stall[5] == `NoStop)),
    .waddr(wb_wd_i),
    .wdata(wb_wdata_i),
    .re1(reg1_read),
    .raddr1(reg1_addr),
    .rdata1(reg1_data),
    .re2(reg2_read),
    .raddr2(reg2_addr),
    .rdata2(reg2_data)
    );
    
    //ID/EX模块例化
    id_ex id_ex0(
    .clk(clk),
    .rst(rst),
    //从译码阶段ID模块传递过来的信息
    .id_aluop(id_aluop_o),
    .id_alusel(id_alusel_o),
    .id_reg1(id_reg1_o),
    .id_reg2(id_reg2_o),
    .id_wd(id_wd_o),
    .id_wreg(id_wreg_o),
    .id_is_in_delayslot(id_is_in_delayslot_o),
    .id_link_address(id_link_addr_o),
    .id_inst(id_inst_o),
    .ex_inst(ex_inst_i),
    .next_inst_in_delayslot_i(id_next_inst_in_delayslot_o),
    //传递到执行阶段EX模块的信息
    .ex_aluop(ex_aluop_i),
    .ex_alusel(ex_alusel_i),
    .ex_reg1(ex_reg1_i),
    .ex_reg2(ex_reg2_i),
    .ex_wd(ex_wd_i),
    .ex_wreg(ex_wreg_i),
    .stall(stall),
    .ex_is_in_delayslot(ex_is_in_delayslot_i),
    .ex_link_address(ex_link_address_i),
    .is_in_delayslot_o(is_in_delayslot_i)
    );
    
    //EX模块例化
    ex ex0(
    //ports
    .clk(clk),
    .rst(rst),
    .aluop_i(ex_aluop_i),
    .alusel_i(ex_alusel_i),
    .reg1_i(ex_reg1_i),
    .reg2_i(ex_reg2_i),
    .wd_i(ex_wd_i),
    .wreg_i(ex_wreg_i),
    .wd_o(ex_wd_o),
    .wreg_o(ex_wreg_o),
    .wdata_o(ex_wdata_o),
    .hi_i(hi),
    .lo_i(lo),
    .mem_whilo_i(mem_whilo_i),
    .mem_hi_i(mem_hi_o),
    .mem_lo_i(mem_lo_o),
    .wb_whilo_i(wb_whilo_i),
    .wb_hi_i(wb_hi_i),
    .wb_lo_i(wb_lo_i),
    .inst_i(ex_inst_i),
    .aluop_o(ex_aluop_o),
    .mem_addr_o(ex_mem_addr_o),
    .reg2_o(ex_reg2_o),
    .whilo_o(ex_whilo_o),
    .hi_o(ex_hi_o),
    .lo_o(ex_lo_o),
    .stallreq(stallreq_from_ex),
    .cnt_i(cnt_i),
    .hilo_temp_i(hilo_temp_i),
    .cnt_o(cnt_o),
    .hilo_temp_o(hilo_temp_o),
    .link_address_i(ex_link_address_i),
    .is_in_delayslot_i(ex_is_in_delayslot_i),

    // multi-cycle divider handshake
    .div_result_i(div_result),
    .div_ready_i(div_ready),
    .div_opdata1_o(div_opdata1),
    .div_opdata2_o(div_opdata2),
    .div_start_o(div_start),
    .signed_div_o(signed_div)
    );

    // =========================================================================
    // 32-bit multi-cycle divider (replaces the behavioural / and % in ex.v)
    // =========================================================================
    div div0(
    .clk(clk),
    .rst(rst),

    .signed_div_i(signed_div),
    .opdata1_i(div_opdata1),
    .opdata2_i(div_opdata2),
    .start_i(div_start),
    .annul_i(1'b0),

    .result_o(div_result),
    .ready_o(div_ready)
    );
    
    
    //EX/MEM模块例化
    ex_mem ex_mem0(
    //ports
    .clk(clk),
    .rst(rst),
    .stall(stall),
    .ex_wd(ex_wd_o),
    .ex_wreg(ex_wreg_o),
    .ex_wdata(ex_wdata_o),
    .ex_whilo(ex_whilo_o),
    .ex_hi(ex_hi_o),
    .ex_lo(ex_lo_o),
    .ex_aluop(ex_aluop_o),
    .ex_mem_addr(ex_mem_addr_o),
    .ex_reg2(ex_reg2_o),
    .mem_whilo(mem_whilo_i),
    .mem_hi(mem_hi_i),
    .mem_lo(mem_lo_i),
    .mem_wd(mem_wd_i),
    .mem_wreg(mem_wreg_i),
    .mem_wdata(mem_wdata_i),
    .mem_aluop(mem_aluop_i),
    .mem_mem_addr(mem_mem_addr_i),
    .mem_reg2(mem_reg2_i),
    .cnt_i(cnt_o),
    .hilo_i(hilo_temp_o),
    .cnt_o(cnt_i),
    .hilo_o(hilo_temp_i)
    );
    
    //MEM模块例化
    mem mem0(
    //ports
    .rst(rst),
    .wd_i(mem_wd_i),
    .wreg_i(mem_wreg_i),
    .wdata_i(mem_wdata_i),
    .wd_o(mem_wd_o),
    .wreg_o(mem_wreg_o),
    .wdata_o(mem_wdata_o),
    .whilo_i(mem_whilo_i),
    .hi_i(mem_hi_i),
    .lo_i(mem_lo_i),
    .whilo_o(mem_whilo_o),
    .hi_o(mem_hi_o),
    .lo_o(mem_lo_o),
    .aluop_i(mem_aluop_i),
    .mem_addr_i(mem_mem_addr_i),
    .reg2_i(mem_reg2_i),
    .mem_data_i(ram_data_i),
    .mem_addr_o(ram_addr_o),
    .mem_we_o(ram_we_o),
    .mem_sel_o(ram_sel_o),
    .mem_data_o(ram_data_o),
    .mem_ce_o(ram_ce_o)
    );
    
    //MEM/WB模块例化
    mem_wb mem_wb0(
    //ports
    .clk(clk),
    .rst(rst),
    .mem_wd(mem_wd_o),
    .mem_wreg(mem_wreg_o),
    .mem_wdata(mem_wdata_o),
    .wb_wd(wb_wd_i),
    .wb_wreg(wb_wreg_i),
    .wb_wdata(wb_wdata_i),
    .mem_whilo(mem_whilo_o),
    .mem_hi(mem_hi_o),
    .mem_lo(mem_lo_o),
    .wb_whilo(wb_whilo_i),
    .wb_hi(wb_hi_i),
    .wb_lo(wb_lo_i),
    .stall(stall)
    );
    
    //hilo_reg模块例化
    hilo_reg hilo_reg0(
    //ports
    .rst(rst),
    .clk(clk),
    .we (wb_whilo_i & (stall[5] == `NoStop)),
    .hi_i(wb_hi_i),
    .lo_i(wb_lo_i),
    .hi_o(hi),
    .lo_o(lo)
    );
    
    // ctrl模块
    ctrl ctrl0(
    //ports
    .rst(rst),
    .stallreq_from_id(stallreq_from_id),
    .stallreq_from_ex(stallreq_from_ex),
    .stallreq_from_dbg(dbg_stall_i),
    .stall(stall)
    );


`ifndef SYNTHESIS
    // =========================================================================
    // Simulation-only Pipeline Stage Trackers & Performance Counters
    // =========================================================================
    wire        fetch_valid     = rom_ce_o & (rom_data_i != 32'd0);
    wire [31:0] if_id_pc        = id_pc_i;
    wire        if_id_valid     = (id_inst_i != 32'd0);
    wire        load_use_stall  = stallreq_from_id;
    wire        div_stall       = stallreq_from_ex;
    wire        ex_branch_taken = 1'b0;
    wire        id_jal_taken    = 1'b0;

    wire [1:0] id_fwd_a = (!if_id_valid || !reg1_read || (reg1_addr == 5'd0)) ? 2'b00 :
                          (ex_wreg_o && (ex_wd_o == reg1_addr)) ? 2'b10 :
                          (mem_wreg_o && (mem_wd_o == reg1_addr)) ? 2'b01 : 2'b00;
    wire [1:0] id_fwd_b = (!if_id_valid || !reg2_read || (reg2_addr == 5'd0)) ? 2'b00 :
                          (ex_wreg_o && (ex_wd_o == reg2_addr)) ? 2'b10 :
                          (mem_wreg_o && (mem_wd_o == reg2_addr)) ? 2'b01 : 2'b00;

    reg [31:0] id_ex_pc;
    reg        id_ex_valid;
    reg [4:0]  id_ex_rs1;
    reg [4:0]  id_ex_rs2;
    reg [4:0]  id_ex_rd;
    reg [1:0]  fwd_a;
    reg [1:0]  fwd_b;
    reg [31:0] ex_mem_pc;
    reg        ex_mem_valid;
    reg [31:0] mem_wb_pc;
    reg        mem_wb_valid;

    always @(posedge clk) begin
        if (rst == `RstEnable) begin
            id_ex_pc     <= 32'd0;
            id_ex_valid  <= 1'b0;
            id_ex_rs1    <= 5'd0;
            id_ex_rs2    <= 5'd0;
            id_ex_rd     <= 5'd0;
            fwd_a        <= 2'b00;
            fwd_b        <= 2'b00;
            ex_mem_pc    <= 32'd0;
            ex_mem_valid <= 1'b0;
            mem_wb_pc    <= 32'd0;
            mem_wb_valid <= 1'b0;
        end else begin
            if (stall[2] == `Stop && stall[3] == `NoStop) begin
                id_ex_pc    <= 32'd0;
                id_ex_valid <= 1'b0;
                id_ex_rs1   <= 5'd0;
                id_ex_rs2   <= 5'd0;
                id_ex_rd    <= 5'd0;
                fwd_a       <= 2'b00;
                fwd_b       <= 2'b00;
            end else if (stall[2] == `NoStop) begin
                id_ex_pc    <= if_id_pc;
                id_ex_valid <= if_id_valid;
                id_ex_rs1   <= reg1_addr;
                id_ex_rs2   <= reg2_addr;
                id_ex_rd    <= id_wd_o;
                fwd_a       <= id_fwd_a;
                fwd_b       <= id_fwd_b;
            end
            if (stall[3] == `Stop && stall[4] == `NoStop) begin
                ex_mem_pc    <= 32'd0;
                ex_mem_valid <= 1'b0;
            end else if (stall[3] == `NoStop) begin
                ex_mem_pc    <= id_ex_pc;
                ex_mem_valid <= id_ex_valid;
            end
            if (stall[4] == `Stop && stall[5] == `NoStop) begin
                mem_wb_pc    <= 32'd0;
                mem_wb_valid <= 1'b0;
            end else if (stall[4] == `NoStop) begin
                mem_wb_pc    <= ex_mem_pc;
                mem_wb_valid <= ex_mem_valid;
            end
        end
    end

    reg [31:0] rtl_cycle_cnt;
    reg [31:0] rtl_inst_retired;
    reg [31:0] rtl_mem_done;
    reg [31:0] rtl_load_stalls;
    reg [31:0] rtl_div_stalls;
    reg [31:0] rtl_ex_fwds;
    reg [31:0] rtl_mem_fwds;
    reg [31:0] rtl_branch_flushes;

    wire       pipe_active  = fetch_valid | if_id_valid | id_ex_valid | ex_mem_valid | mem_wb_valid;
    wire       fwd_count_en = id_ex_valid && (stall[3] == `NoStop);
    wire       fwd_b_unique = (id_ex_rs2 != id_ex_rs1) || (fwd_a != fwd_b);
    wire [1:0] ex_fwd_inc   = ((fwd_a == 2'b10) ? 2'd1 : 2'd0) + (((fwd_b == 2'b10) && fwd_b_unique) ? 2'd1 : 2'd0);
    wire [1:0] mem_fwd_inc  = ((fwd_a == 2'b01) ? 2'd1 : 2'd0) + (((fwd_b == 2'b01) && fwd_b_unique) ? 2'd1 : 2'd0);

    always @(posedge clk) begin
        if (rst == `RstEnable) begin
            rtl_cycle_cnt      <= 32'd0;
            rtl_inst_retired   <= 32'd0;
            rtl_mem_done       <= 32'd0;
            rtl_load_stalls    <= 32'd0;
            rtl_div_stalls     <= 32'd0;
            rtl_ex_fwds        <= 32'd0;
            rtl_mem_fwds       <= 32'd0;
            rtl_branch_flushes <= 32'd0;
        end else if (pipe_active) begin
            rtl_cycle_cnt    <= rtl_cycle_cnt + 32'd1;
            rtl_inst_retired <= rtl_inst_retired + {31'd0, mem_wb_valid};
            rtl_mem_done     <= rtl_mem_done + {31'd0, (ex_mem_valid & (stall[4] == `NoStop))};
            rtl_load_stalls  <= rtl_load_stalls + {31'd0, load_use_stall};
            rtl_div_stalls   <= rtl_div_stalls + {31'd0, div_stall};
            if (fwd_count_en) begin
                rtl_ex_fwds  <= rtl_ex_fwds + {30'd0, ex_fwd_inc};
                rtl_mem_fwds <= rtl_mem_fwds + {30'd0, mem_fwd_inc};
            end
        end
    end
`endif

endmodule ///home/groot/openmips
