#

__title__ = "FreeCAD Frame3DD library"
__author__ = "John Wang based on importCcxFrdResults.py" 

## @package importFrame3DDCase
#  \ingroup FEM
#  \brief FreeCAD Frame3DD Reader for FEM workbench

import FreeCAD
from FreeCAD import Console
import os


# ********* generic FreeCAD import and export methods *********
if open.__module__ == "__builtin__":
    # because we'll redefine open below (Python2)
    pyopen = open
elif open.__module__ == "io":
    # because we'll redefine open below (Python3)
    pyopen = open


def open(filename):
    "called when freecad opens a file"
    docname = os.path.splitext(os.path.basename(filename))[0]
    insert(filename, docname)


def insert(
    filename,
    docname
):
    "called when freecad wants to import a file"
    try:
        doc = FreeCAD.getDocument(docname)
    except NameError:
        doc = FreeCAD.newDocument(docname)
    FreeCAD.ActiveDocument = doc
    importFrame3DDCase(filename)
	
# ********* module specific methods *********
def importFrame3DDCase(
    filename,
    analysis=None,
    result_name_prefix=""
):
    from . import importToolsFem
    import ObjectsFem

    m = read_Frame3DD_case(filename)
    result_mesh_object = None
    if len(m["Nodes"]) > 0:
        mesh = importToolsFem.make_femmesh(m)
        result_mesh_object = ObjectsFem.makeMeshResult(
            FreeCAD.ActiveDocument,
            "ResultMesh"
        )
        result_mesh_object.FemMesh = mesh
        res_mesh_is_compacted = False
        nodenumbers_for_compacted_mesh = []

        number_of_increments = len(m["Results"])
        Console.PrintLog(
            "Increments: " + str(number_of_increments) + "\n"
        )
        if len(m["Results"]) > 0:
            for result_set in m["Results"]:
                if "number" in result_set:
                    eigenmode_number = result_set["number"]
                else:
                    eigenmode_number = 0
                step_time = result_set["time"]
                step_time = round(step_time, 2)
                if eigenmode_number > 0:
                    results_name = (
                        "{}Mode{}_Results"
                        .format(result_name_prefix, eigenmode_number)
                    )
                elif number_of_increments > 1:
                    results_name = (
                        "{}Time{}_Results"
                        .format(result_name_prefix, step_time)
                    )
                else:
                    results_name = (
                        "{}Results"
                        .format(result_name_prefix)
                    )

                res_obj = ObjectsFem.makeResultMechanical(FreeCAD.ActiveDocument, results_name)
                res_obj.Mesh = result_mesh_object
                res_obj = importToolsFem.fill_femresult_mechanical(res_obj, result_set)
                if analysis:
                    analysis.addObject(res_obj)

                # complementary result object calculations
                import femresult.resulttools as restools
                import femtools.femutils as femutils
                if not res_obj.MassFlowRate:
                    # information 1:
                    # only compact result if not Flow 1D results
                    # compact result object, workaround for bug 2873
                    # https://www.freecadweb.org/tracker/view.php?id=2873
                    # information 2:
                    # if the result data has multiple result sets there will be multiple result objs
                    # they all will use one mesh obj
                    # on the first res obj fill the mesh obj will be compacted, thus
                    # it does not need to be compacted on further result sets
                    # but NodeNumbers need to be compacted for every result set (res object fill)
                    # example Frame3DD file: https://forum.freecadweb.org/viewtopic.php?t=32649#p274291
                    if res_mesh_is_compacted is False:
                        # first result set, compact FemMesh and NodeNumbers
                        res_obj = restools.compact_result(res_obj)
                        res_mesh_is_compacted = True
                        nodenumbers_for_compacted_mesh = res_obj.NodeNumbers
                    else:
                        # all other result sets, do not compact FemMesh, only set NodeNumbers
                        res_obj.NodeNumbers = nodenumbers_for_compacted_mesh

                # fill DisplacementLengths
                res_obj = restools.add_disp_apps(res_obj)
                # fill StressValues
                res_obj = restools.add_von_mises(res_obj)
                if res_obj.getParentGroup():
                    has_reinforced_mat = False
                    for obj in res_obj.getParentGroup().Group:
                        if obj.isDerivedFrom("App::MaterialObjectPython") \
                                and femutils.is_of_type(obj, "Fem::MaterialReinforced"):
                            has_reinforced_mat = True
                            restools.add_principal_stress_reinforced(res_obj)
                            break
                    if has_reinforced_mat is False:
                        # fill PrincipalMax, PrincipalMed, PrincipalMin, MaxShear
                        res_obj = restools.add_principal_stress_std(res_obj)
                else:
                    # if a pure Frame3DD file was opened no analysis and thus no parent group
                    # fill PrincipalMax, PrincipalMed, PrincipalMin, MaxShear
                    res_obj = restools.add_principal_stress_std(res_obj)
                # fill Stats
                res_obj = restools.fill_femresult_stats(res_obj)
                return res_obj


        else:
            error_message = (
                "We have nodes but no results in Frame3DD file, "
                "which means we only have a mesh in Frame3DD file. "
                "Usually this happens for analysis type 'NOANALYSIS' "
                "or if Frame3DD returned no results because "
                "of nonpositive jacobian determinant in at least one element.\n"
            )
            Console.PrintMessage(error_message)
            if analysis:
                analysis.addObject(result_mesh_object)

        if FreeCAD.GuiUp:
            if analysis:
                import FemGui
                FemGui.setActiveAnalysis(analysis)
            FreeCAD.ActiveDocument.recompute()

    else:
        Console.PrintError(
            "Problem on Frame3DD file import. No nodes found in Frame3DD file.\n"
        )


# read a Frame3DD result file and extract the nodes
# displacement vectors and stress values.
def read_Frame3DD_case(
    Frame3DD_input
):
    Console.PrintMessage(
        "Read Frame3DD results from Frame3DD file: {}\n"
        .format(Frame3DD_input)
    )
    inout_nodes = []
    inout_nodes_file = Frame3DD_input.rsplit(".", 1)[0] + "_inout_nodes.txt"
    if os.path.exists(inout_nodes_file):
        Console.PrintMessage(
            "Read special 1DFlow nodes data form: {}\n".format(inout_nodes_file)
        )
        f = pyopen(inout_nodes_file, "r")
        lines = f.readlines()
        for line in lines:
            a = line.split(",")
            inout_nodes.append(a)
        f.close()
        Console.PrintMessage("{}\n".format(inout_nodes))
    Frame3DD_file = pyopen(Frame3DD_input, "r")
    nodes = {}
    elements_hexa8 = {}
    elements_penta6 = {}
    elements_tetra4 = {}
    elements_tetra10 = {}
    elements_penta15 = {}
    elements_hexa20 = {}
    elements_tria3 = {}
    elements_tria6 = {}
    elements_quad4 = {}
    elements_quad8 = {}
    elements_seg2 = {}
    elements_seg3 = {}
    results = []
    mode_results = {}
    mode_results["number"] = float("NaN")
    mode_results["time"] = float("NaN")
    mode_disp = {}
    mode_stress = {}
    mode_strain = {}
    mode_peeq = {}
    mode_temp = {}
    mode_massflow = {}
    mode_networkpressure = {}

    nodes_found = False
    elements_found = False
    mode_time_found = False
    mode_disp_found = False
    mode_stress_found = False
    mode_strain_found = False
    mode_peeq_found = False
    mode_temp_found = False
    mode_massflow_found = False
    mode_networkpressure_found = False
    end_of_section_found = False
    end_of_Frame3DD_data_found = False
    input_continues = False
    mode_eigen_changed = False
    mode_time_changed = False

    eigenmode = 0
    eigentemp = 0
    elem = -1
    elemType = 0
    timestep = 0
    timetemp = 0

    tline=[]
    for line in Frame3DD_file:
        tline.append(line.strip())
		
    i=1	
    #Console.PrintError(tline[i]+'\n')
		
	#node 1111111111111111111111111111111111111111111111111111111
    while 1:
        i=i+1
        #print (tline[i])
        if len(tline[i])==0 or tline[i][0]=='#':
            continue
        else:
            break


    print ("")			
    data = tline[i].split()
    numNode =  int(data[0])
    print ("numNode: "+str(numNode))


    while 1:
        i=i+1
        #print (tline[i])
        if len(tline[i])==0 or tline[i][0]=='#':
            continue
        else:
            break

    print (tline[i])
    dataNode = tline[i].split()

    elem = int(dataNode[0])
    nodes_x = float(dataNode[1])
    nodes_y = float(dataNode[2])
    nodes_z = float(dataNode[3])
    nodes[elem] = FreeCAD.Vector(nodes_x, nodes_y, nodes_z)

    for id in range(1,numNode): # node
	    #1       0.000000       0.000000       0.000000    0.000   1  1  1  1  1  0
        while 1:
            i=i+1
            #print (tline[i])
            if len(tline[i])==0 or tline[i][0]=='#':
                continue
            else:
                break
        print (tline[i])
        dataNode = tline[i].split()

        elem = int(dataNode[0])
        nodes_x = float(dataNode[1])
        nodes_y = float(dataNode[2])
        nodes_z = float(dataNode[3])
        nodes[elem] = FreeCAD.Vector(nodes_x, nodes_y, nodes_z)

    #number of nodes with reactions 22222222222222222222222222222222222222222
    while 1:
        i=i+1
        #print (tline[i])
        if len(tline[i])==0 or tline[i][0]=='#':
            continue
        else:
            break


    print ("")			
    data = tline[i].split()
    numReaction =  int(data[0])
    print ("numReaction: "+str(numReaction))

    if (numReaction>0):
        while 1:
            i=i+1
            #print (tline[i])
            if len(tline[i])==0 or tline[i][0]=='#':
                continue
            else:
                break


        print (tline[i])
        dataReaction = tline[i].split()

        #elem = int(dataReaction[0])
        #nodes_x = float(dataReaction[1])
        #nodes_y = float(dataReaction[2])
        #nodes_z = float(dataReaction[3])
        #nodes[elem] = FreeCAD.Vector(nodes_x, nodes_y, nodes_z)

        for id in range(1,numReaction): # node
            #1       0.000000       0.000000       0.000000    0.000   1  1  1  1  1  0
            #i=i+1
            while 1:
                i=i+1
                #print (tline[i])
                if len(tline[i])==0 or tline[i][0]=='#':
                    continue
                else:
                    break
            print (tline[i])
            #dataNode = tline[i].split()

            #elem = int(dataNode[0])
            #nodes_x = float(dataNode[1])
            #nodes_y = float(dataNode[2])
            #nodes_z = float(dataNode[3])
            #nodes[elem] = FreeCAD.Vector(nodes_x, nodes_y, nodes_z)
	
	
    #Member 333333333333333333333333333333333333333333333333333333
    while 1:
        i=i+1
        #print (tline[i])
        if len(tline[i])==0 or tline[i][0]=='#':
            continue
        else:
            break

    print ("")			
    data = tline[i].split()
    numMember =  int(data[0])
    print ("numMember: "+str(numMember))

    while 1:
        i=i+1
        #print (tline[i])
        if len(tline[i])==0 or tline[i][0]=='#':
            continue
        else:
            break
		
    print (tline[i])
    dataNode = tline[i].split()
    elem = int(dataNode[0])
    nd1 = int(dataNode[1])
    nd2 = int(dataNode[2])
    elements_seg2[elem] = (nd1, nd2)
    for id in range(1,numMember): # Member
        #i=i+1
        while 1:
            i=i+1
            #print (tline[i])
            if len(tline[i])==0 or tline[i][0]=='#':
                continue
            else:
                break
        print (tline[i])
        dataNode = tline[i].split()
        elem = int(dataNode[0])
        nd1 = int(dataNode[1])
        nd2 = int(dataNode[2])
        elements_seg2[elem] = (nd1, nd2)


        # here we are in the indent of loop for every line in Frame3DD file
        # do not add a print here :-)

    # close Frame3DD file if loop over all lines is finished
    Frame3DD_file.close()

    """
    # debug prints and checks with the read data
    print("\n\n----RESULTS values begin----")
    print(len(results))
    # print("\n")
    # print(results)
    print("----RESULTS values end----\n\n")
    """

    if not inout_nodes:
        if results:
            if "mflow" in results[0] or "npressure" in results[0]:
                Console.PrintError(
                    "We have mflow or npressure, but no inout_nodes file.\n"
                )
    if not nodes:
        Console.PrintError("FEM: No nodes found in Frame3DD file.\n")

    return {
        "Nodes": nodes,
        "Seg2Elem": elements_seg2,
        "Seg3Elem": elements_seg3,
        "Tria3Elem": elements_tria3,
        "Tria6Elem": elements_tria6,
        "Quad4Elem": elements_quad4,
        "Quad8Elem": elements_quad8,
        "Tetra4Elem": elements_tetra4,
        "Tetra10Elem": elements_tetra10,
        "Hexa8Elem": elements_hexa8,
        "Hexa20Elem": elements_hexa20,
        "Penta6Elem": elements_penta6,
        "Penta15Elem": elements_penta15,
        "Results": results
    }
