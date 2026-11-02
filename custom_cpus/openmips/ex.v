/*
 * @Author: Groot
 * @Date: 2022-04-09 18:01:23
 * @LastEditTime: 2022-05-14 16:47:57
 * @LastEditors: Groot
 * @Description:
 * @FilePath: /openMIPS/vsrc/ex.v
 * 版权声明
 */
`include "define.v"

module ex (input wire clk,
           input wire rst,                  //译码阶段送到执行阶段的信息
           input wire[`AluOpBus] aluop_i,
           input wire[`AluSelBus] alusel_i,
           input wire[`RegBus] reg1_i,
           input wire[`RegBus] reg2_i,
           input wire[`RegAddBus] wd_i,
           input wire wreg_i,
           output reg[`RegAddBus] wd_o,     //执行的结果
           output reg wreg_o,
           output reg[`RegBus] wdata_o,
           input wire[`RegBus] hi_i,        //HILO模块给出的HI寄存器的值
           input wire[`RegBus] lo_i,        //HILO模块给出的LO寄存器的值
           input wire mem_whilo_i,          //处于访存阶段的指令是否要写HI、LO寄存器
           input wire[`RegBus] mem_hi_i,    //处于访存阶段的指令要写入的HI寄存器的值
           input wire[`RegBus] mem_lo_i,    //处于访存阶段的指令要写入的LO寄存器的值
           input wire wb_whilo_i,           //处于写回阶段的指令是否要写HI、LO寄存器
           input wire[`RegBus] wb_hi_i,     //处于写回阶段的指令要写入的HI寄存器的值
           input wire[`RegBus] wb_lo_i,     //处于写回阶段的指令要写入的LO寄存器的值
           output reg whilo_o,              //处于执行阶段的指令是否要写HI、LO寄存器
           output reg[`RegBus] hi_o,        //处于执行阶段的指令要写入的HI寄存器的值
           output reg[`RegBus] lo_o,        //处于执行阶段的指令要写入的LO寄存器的值
           output reg stallreq,

           input wire[`DoubleRegBus] hilo_temp_i,
           input wire[1:0] cnt_i,
           output reg[`DoubleRegBus] hilo_temp_o,
           output reg[1:0] cnt_o,

           input wire is_in_delayslot_i,
           input wire[`RegBus] link_address_i,

           input wire[`RegBus] inst_i,
           output wire[`AluOpBus] aluop_o,
           output wire[`RegBus] mem_addr_o,
           output wire[`RegBus] reg2_o,

           // ---- multi-cycle divider handshake (see div.v) ----
           input  wire[`DoubleRegBus] div_result_i,
           input  wire                div_ready_i,
           output reg[`RegBus]        div_opdata1_o,
           output reg[`RegBus]        div_opdata2_o,
           output reg                 div_start_o,
           output reg                 signed_div_o
           );            
    
    reg[`RegBus] logicout;      //逻辑操作的结果
    reg[`RegBus] shiftres;      //以为操作的结果
    reg[`RegBus] movres;        //移动操作的结果
    reg[`RegBus] HI;            //保存HI寄存器的最新值
    reg[`RegBus] LO;            //保存LO寄存器的最新值
    
    //定义了一些新变量
    wire ov_sum;                    // 保存溢出结果
    wire reg1_eq_reg2;              // 第一个操作数是否等于第二个操作数
    wire reg1_lt_reg2;              // 第一个操作数是否小于第二个操作数
    reg[`RegBus] arithmeticres;     // 保存算术运算的结果
    wire[`RegBus] reg2_i_mux;       // 保存输入的第二个操作数reg2_i的补码
    wire[`RegBus] reg1_i_not;       // 保存输入的第一个操作数reg1_i的反码
    wire[`RegBus] result_sum;       // 保存加法结果
    wire[`RegBus] opdata1_mult;     // 乘法操作中的被乘数
    wire[`RegBus] opdata2_mult;     // 乘法操作中的乘数
    wire[`DoubleRegBus] hilo_temp;  // 临时保存乘法结果，宽度为64位
    reg[`DoubleRegBus] hilo_temp1;  // 临时保存累乘加减的结果
    reg stallreq_for_madd_msub;     // 累乘加减发出的流水线暂停请求
    reg stallreq_for_div;           // 多周期除法器发出的流水线暂停请求
    reg[`DoubleRegBus] mulres;      // 保存乘法结果，宽度为64位
    
    assign aluop_o = aluop_i;
    assign reg2_o  = reg2_i;
    assign mem_addr_o = reg1_i + {{16{inst_i[15]}},inst_i[15:0]};

    /*****************************************第一段：计算以下五个变量的值**************************************/
    // 1.如果是减法或者有符号比较运算，那么第二个操作数需要使用补码
    //   否则，第二个操作数仍等于它自身
    assign reg2_i_mux = ((aluop_i == `EXE_SUB_OP) || (aluop_i == `EXE_SLT_OP) || (aluop_i == `EXE_SUBU_OP))? (~reg2_i)+1 : reg2_i;
    // 2. 分三种情况
    //      a. 如果是加法运算，那么reg2_i_mux就是第二个操作数reg2_i。所以result_sum就是加运算的结果
    //      b. 如果是减法运算，此时reg2_i_mux的值为第二个操作数reg2_i的补码。所以result_sum就是减法运算的结果
    //      c. 如果是有符号比较运算，此时reg2_i_mux的值也是第二个操作数reg2_i的补码。所以result_sum就是减法运算的结果，
    //         可以通过判断result_sum是否小于零，进而判断第一个操作数是否小于第二个操作数。
    assign result_sum = reg1_i + reg2_i_mux;
    // 3. 计算是否溢出
    //    加法指令add/addi和减法指令执行的时候需要判断是否溢出
    //    满足以下两种情况之一时，会产生溢出
    //        a. reg1_i为正数，reg2_i_mux为正数，但二者之和为负数
    //        b. reg1_i为负数，reg2_i_mux为负数，但二者之和为整数
    assign ov_sum = ((!reg1_i[31] && !reg2_i_mux[31]) && result_sum[31]) || ((reg1_i[31] && reg2_i_mux[31]) && !result_sum[31]);
    // 4. 计算操作数1是否小于操作数2，有符号/无符号比较
    assign reg1_lt_reg2 = ((aluop_i == `EXE_SLT_OP) ? 
                           ($signed(reg1_i) < $signed(reg2_i)) : 
                           (reg1_i < reg2_i));
    // 5. 对操作数1按位取反，赋值给reg1_i_not
    assign reg1_i_not = ~reg1_i;
    /*****************************************第二段：依据不同的算术运算类型，给arithmetices变量赋值**************************************/
    always @ (*) begin
        if (rst == `RstEnable) begin
            arithmeticres <= `ZeroWord;
        end
        else begin
            case(aluop_i)
                `EXE_SLT_OP, `EXE_SLTU_OP : begin
                    arithmeticres <= reg1_lt_reg2;
                end
                `EXE_ADD_OP, `EXE_ADDU_OP : begin
                    arithmeticres <= result_sum;
                end
                `EXE_SUB_OP, `EXE_SUBU_OP : begin
                    arithmeticres <= result_sum;
                end
                `EXE_CLO_OP : begin
                    arithmeticres <= reg1_i_not[31] ? 0 : reg1_i_not[30] ? 1 :
                                     reg1_i_not[29] ? 2 : reg1_i_not[28] ? 3 :
                                     reg1_i_not[27] ? 4 : reg1_i_not[26] ? 5 :
                                     reg1_i_not[25] ? 6 : reg1_i_not[24] ? 7 :
                                     reg1_i_not[23] ? 8 : reg1_i_not[22] ? 9 :
                                     reg1_i_not[21] ? 10 : reg1_i_not[20] ? 11 :
                                     reg1_i_not[19] ? 12 : reg1_i_not[18] ? 13 :
                                     reg1_i_not[17] ? 14 : reg1_i_not[16] ? 15 :
                                     reg1_i_not[15] ? 16 : reg1_i_not[14] ? 17 :
                                     reg1_i_not[13] ? 18 : reg1_i_not[12] ? 19 :
                                     reg1_i_not[11] ? 20 : reg1_i_not[10] ? 21 :
                                     reg1_i_not[9] ? 22 : reg1_i_not[8] ? 23 :
                                     reg1_i_not[7] ? 24 : reg1_i_not[6] ? 25 :
                                     reg1_i_not[5] ? 26 : reg1_i_not[4] ? 27 :
                                     reg1_i_not[3] ? 28 : reg1_i_not[2] ? 29 :
                                     reg1_i_not[1] ? 30 : reg1_i_not[0] ? 31 : 32;
                end
                `EXE_CLZ_OP : begin
                    arithmeticres <= reg1_i[31] ? 0 : reg1_i[30] ? 1 :
                                     reg1_i[29] ? 2 : reg1_i[28] ? 3 :
                                     reg1_i[27] ? 4 : reg1_i[26] ? 5 :
                                     reg1_i[25] ? 6 : reg1_i[24] ? 7 :
                                     reg1_i[23] ? 8 : reg1_i[22] ? 9 :
                                     reg1_i[21] ? 10 : reg1_i[20] ? 11 :
                                     reg1_i[19] ? 12 : reg1_i[18] ? 13 :
                                     reg1_i[17] ? 14 : reg1_i[16] ? 15 :
                                     reg1_i[15] ? 16 : reg1_i[14] ? 17 :
                                     reg1_i[13] ? 18 : reg1_i[12] ? 19 :
                                     reg1_i[11] ? 20 : reg1_i[10] ? 21 :
                                     reg1_i[9] ? 22 : reg1_i[8] ? 23 :
                                     reg1_i[7] ? 24 : reg1_i[6] ? 25 :
                                     reg1_i[5] ? 26 : reg1_i[4] ? 27 :
                                     reg1_i[3] ? 28 : reg1_i[2] ? 29 :
                                     reg1_i[1] ? 30 : reg1_i[0] ? 31 : 32;
                                     
                end
                default : begin
                    arithmeticres <= `ZeroWord;
                end
            endcase
        end
    end

    /*****************************************第三段：进行乘法运算**************************************/
    wire signed [63:0] mult_signed = $signed(reg1_i) * $signed(reg2_i);
    wire [63:0] mult_unsigned = reg1_i * reg2_i;
    wire is_signed_mult = (aluop_i == `EXE_MUL_OP || aluop_i == `EXE_MULT_OP || aluop_i == `EXE_MADD_OP || aluop_i == `EXE_MSUB_OP);

    always @(*) begin
        if (rst == `RstEnable) begin
            mulres <= {`ZeroWord, `ZeroWord};
        end
        else if (is_signed_mult) begin
            mulres <= mult_signed;
        end
        else begin
            mulres <= mult_unsigned;
        end
    end

    // ***************************** 多周期除法器控制 *****************************
    always @(*) begin
        if (rst == `RstEnable) begin
            stallreq_for_div <= `NoStop;
            div_opdata1_o    <= `ZeroWord;
            div_opdata2_o    <= `ZeroWord;
            div_start_o      <= 1'b0;
            signed_div_o     <= 1'b0;
        end else begin
            stallreq_for_div <= `NoStop;
            div_opdata1_o    <= `ZeroWord;
            div_opdata2_o    <= `ZeroWord;
            div_start_o      <= 1'b0;
            signed_div_o     <= 1'b0;
            case (aluop_i)
                `EXE_DIV_OP: begin
                    div_opdata1_o <= reg1_i;
                    div_opdata2_o <= reg2_i;
                    signed_div_o  <= 1'b1;
                    if (div_ready_i == 1'b0) begin
                        div_start_o      <= 1'b1;
                        stallreq_for_div <= `Stop;
                    end
                end
                `EXE_DIVU_OP: begin
                    div_opdata1_o <= reg1_i;
                    div_opdata2_o <= reg2_i;
                    signed_div_o  <= 1'b0;
                    if (div_ready_i == 1'b0) begin
                        div_start_o      <= 1'b1;
                        stallreq_for_div <= `Stop;
                    end
                end
                default: begin
                end
            endcase
        end
    end

    // 暂停流水线
    always @(*) begin
        stallreq <= stallreq_for_madd_msub | stallreq_for_div;
    end

    // *********************************************累乘加、累乘减*********************************************
    always @(*) begin
        if(rst == `RstEnable) begin
            hilo_temp_o                 <= {`ZeroWord, `ZeroWord};
            cnt_o                       <= 2'b00;
            hilo_temp1                  <= {`ZeroWord, `ZeroWord};
            stallreq_for_madd_msub      <= `NoStop;
        end
        else begin
            hilo_temp_o                 <= {`ZeroWord, `ZeroWord};
            cnt_o                       <= 2'b00;
            hilo_temp1                  <= {`ZeroWord, `ZeroWord};
            stallreq_for_madd_msub      <= `NoStop;
            case (aluop_i)
                `EXE_MADD_OP, `EXE_MADDU_OP : begin
                    if (cnt_i == 2'b00) begin       // 执行阶段的第一个时钟周期
                        hilo_temp_o                 <= mulres;
                        cnt_o                       <= 2'b01;
                        hilo_temp1                  <=  {`ZeroWord, `ZeroWord};
                        stallreq_for_madd_msub      <= `Stop;
                    end
                    else if (cnt_i == 2'b01) begin  // 执行阶段的第二个时钟周期
                        hilo_temp_o                 <= {`ZeroWord, `ZeroWord};;
                        cnt_o                       <= 2'b10;
                        hilo_temp1                  <=  hilo_temp_i + {HI, LO};
                        stallreq_for_madd_msub      <= `NoStop;
                    end
                end
                `EXE_MSUB_OP, `EXE_MSUBU_OP : begin
                    if (cnt_i == 2'b00) begin       // 执行阶段的第一个时钟周期
                        hilo_temp_o                 <= ~mulres + 1;
                        cnt_o                       <= 2'b01;
                        hilo_temp1                  <=  {`ZeroWord, `ZeroWord};
                        stallreq_for_madd_msub      <= `Stop;
                    end
                    else if (cnt_i == 2'b01) begin  // 执行阶段的第二个时钟周期
                        hilo_temp_o                 <= {`ZeroWord, `ZeroWord};;
                        cnt_o                       <= 2'b10;
                        hilo_temp1                  <=  hilo_temp_i + {HI, LO};
                        stallreq_for_madd_msub      <= `NoStop;
                    end
                end
                default : begin
                    hilo_temp_o                 <= {`ZeroWord, `ZeroWord};;
                    cnt_o                       <= 2'b00;
                    stallreq_for_madd_msub      <= `NoStop;
                end
            endcase
        end
    end


    //得到最新的HI、LO寄存器的值，此处要解决数据相关问题。
    //如果访存和回写阶段的指令要写HI、LO寄存器，则务必及时更新这两个寄存器
    always @(*) begin
        if (rst == `RstEnable) begin
            {HI, LO} <= {`ZeroWord, `ZeroWord};
        end
        else if (mem_whilo_i == `WriteEnable) begin
            {HI, LO} <= {mem_hi_i, mem_lo_i};           //访存阶段的指令要写HI、LO寄存器
        end
        else if (wb_whilo_i == `WriteEnable) begin
            {HI, LO} <= {wb_hi_i, wb_lo_i};             //回写阶段的指令要写HI、LO寄存器
        end
        else begin
            {HI, LO} <= {hi_i, lo_i};
        end
    end //always
            
    //****************第一段：依据aluop_i指示的运算类型进行运算
    always @(*) begin
        if (rst == `RstEnable) begin
            logicout <= `ZeroWord;
            shiftres <= `ZeroWord;
            movres   <= `ZeroWord;
        end //endif
        else begin
            logicout <= `ZeroWord;
            shiftres <= `ZeroWord;
            movres   <= `ZeroWord;
            case (aluop_i)
                //进行逻辑运算
                `EXE_OR_OP : begin
                    logicout <= reg1_i | reg2_i;
                end
                `EXE_AND_OP : begin
                    logicout <= reg1_i & reg2_i;
                end
                `EXE_NOR_OP : begin
                    logicout <= ~(reg1_i | reg2_i);
                end
                `EXE_XOR_OP : begin
                    logicout <= reg1_i ^ reg2_i;
                end
                //进行位移运算
                //将左操作数按照右操作数指定的位数左移，左操作数移除的位数丢弃，右边补零
                `EXE_SLL_OP : begin
                    shiftres <= reg2_i << reg1_i[4:0];
                end
                `EXE_SRL_OP : begin
                    shiftres <= reg2_i >> reg1_i[4:0];
                end
                //明天看懂这句话
                `EXE_SRA_OP : begin
                    shiftres <= ({32{reg2_i[31]}} << (6'd32-{1'b0,reg1_i[4:0]})) | reg2_i >> reg1_i[4:0];
                end
                //进行移动操作
                `EXE_MOVZ_OP : begin
                    //如果是movz指令，将reg1_i的值作为移动操作的结果
                    movres <= reg1_i;
                end
                `EXE_MOVN_OP : begin
                    //如果是movn指令，将reg1_i的值作为移动操作的结果
                    movres <= reg1_i;
                end
                `EXE_MFHI_OP : begin
                    //如果是mfhi指令，将HI的值作为移动指令的结果
                    movres <= HI;
                end
                `EXE_MFLO_OP : begin
                    //如果是mflo指令，将LO的值作为移动指令的结果
                    movres <= LO;
                end
                default : begin
                    logicout <= `ZeroWord;
                end
            endcase //case aluop_i
        end //end else
    end //end always
    //进行移位运算
    
    //****************第二段：依据alusel_i指示的运算子类型，选择一个运算结果作为最终结果**************
    always @(*) begin
        //wd_o等于wd_i，要写的目的寄存器地址
        wd_o   <= wd_i;                       
        // 如果是add、addi、sub、subi指令，且发生溢出，那么设置wreg_o为WriteDisable，表示不写目的寄存器
        if ((aluop_i == `EXE_ADD_OP || aluop_i == `EXE_SUB_OP) && ov_sum == `OverFlow) begin
            wreg_o <= `WriteDisable;
        end
        else begin
            wreg_o <= wreg_i;
        end

        case (alusel_i)
            //选择逻辑运算结果位最终运算结果
            `EXE_RES_LOGIC : begin
                wdata_o <= logicout;        //wdata_o中存放运算结果
            end
            //选择移位运算结果位最终运算结果
            `EXE_RES_SHIFT : begin
                wdata_o <= shiftres;
            end
            `EXE_RES_MOVE : begin
                wdata_o <= movres;
            end
            `EXE_RES_ARITHMETIC : begin
                wdata_o <= arithmeticres;
            end
            `EXE_RES_MUL : begin
                wdata_o <= mulres;
            end
            `EXE_RES_JUMP_BRANCH : begin
                wdata_o <= link_address_i;
            end
            default : begin
                wdata_o <= `ZeroWord;
            end
        endcase
    end // end always
    
    //如果是MTHI、MTLO指令，那么需要给出whilo_o,hi_o,lo_o的值
    always @(*) begin
        if (rst == `WriteEnable) begin
            whilo_o <= `WriteDisable;
            hi_o    <= `ZeroWord;
            lo_o    <= `ZeroWord;
        end
        else if (aluop_i == `EXE_MADD_OP || aluop_i == `EXE_MADDU_OP) begin
            whilo_o <= `WriteEnable;
            hi_o    <= hilo_temp1[63:32];
            lo_o    <= hilo_temp1[31:0];
        end else if (aluop_i == `EXE_MSUB_OP || aluop_i == `EXE_MSUBU_OP) begin
            whilo_o <= `WriteEnable;
            hi_o    <= hilo_temp1[63:32];
            lo_o    <= hilo_temp1[31:0];
        end
        else if (aluop_i == `EXE_MULT_OP || aluop_i == `EXE_MULTU_OP) begin
            whilo_o <= `WriteEnable;
            hi_o    <= mulres[63:32];
            lo_o    <= mulres[31:0];
        end
        else if (aluop_i == `EXE_DIV_OP || aluop_i == `EXE_DIVU_OP) begin
            // result now arrives from the multi-cycle divider; the pipeline is
            // held by stallreq_for_div until div_ready_i goes high
            whilo_o <= `WriteEnable;
            if (reg2_i == `ZeroWord) begin
                hi_o <= reg1_i;
                lo_o <= 32'hFFFFFFFF;
            end else begin
                hi_o <= div_result_i[63:32];   // remainder
                lo_o <= div_result_i[31:0];    // quotient
            end
        end
        else if (aluop_i == `EXE_MTHI_OP) begin
            //写HI寄存器，所以LO寄存器保持不变
            whilo_o <= `WriteEnable;
            hi_o    <= reg1_i;
            lo_o    <= LO;
        end
        else if (aluop_i == `EXE_MTLO_OP) begin
            //写LO寄存器，所以HI寄存器保持不变
            whilo_o <= `WriteEnable;
            hi_o    <= HI;
            lo_o    <= reg1_i;
            end
        else begin
            whilo_o <= `WriteDisable;
            hi_o    <= `ZeroWord;
            lo_o    <= `ZeroWord;
        end
    end
endmodule //ex
