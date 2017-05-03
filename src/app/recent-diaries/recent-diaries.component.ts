import { Component, OnInit } from '@angular/core';
import { UserService } from '../user.service';
import { ActivatedRoute } from '@angular/router';
import { ImageCyclePipe } from '../image-cycle.pipe';
import { ReversePipe } from '../reverse.pipe';

@Component({
  selector: 'app-recent-diaries',
  templateUrl: './recent-diaries.component.html',
  styleUrls: ['./recent-diaries.component.css']
})
export class RecentDiariesComponent implements OnInit {
  public userId: any;
  public recentDiaries: any;
  public bgTree: any = "../../assets/background/tree_bark.png";
  public showEditForm: boolean = false;

  constructor(
    private userService: UserService,
    private route: ActivatedRoute,
  ) { }

  ngOnInit() {
    this.route.params.forEach((urlParameters) => {
      this.userId = urlParameters['id'];
      //getting diaries of recent
      this.recentDiaries = this.userService.getRecentDiaries(this.userId);
    });
  }

  editDiary(diary){
    this.showEditForm = true;
    console.log(diary.$key);
  }

  deleteDiary(diary){
    if(confirm("You want to delete this diary?")){
      this.userService.deleteDiary(this.userId, diary);
    }
  }

}