if True:
    single_list=[[5, 6], [6, 6], [5, 6], [3, 4], [5, 6], [1, 4]]
    max_team_size=0
    for i in single_list:
        team_size=0
        for j in single_list:
            print(f"{i}: {j}",end=": ")
            # if j[0]>=i[0] and j[1]>=i[1]:
            # if i[0] <= j[0] and i[1] >= j[1]:
            if i[0] <= j[1] and i[1] >= j[0]:
                team_size+=1
                print("o")
            else: print("x")
        if team_size>max_team_size:
            max_team_size=team_size
    print(max_team_size)
